import os
import json
from dotenv import load_dotenv
from mistralai import Mistral

try:
    # When package is used (python -m ai.agent_manager)
    from .precheck import TicketPrechecker
    from .queryanalyser import analyse_query
    from .solutionfinder import solution_finder
    from .deterministic_evaluation import DeterministicEvaluator
    from .response_composer import compose_response
except Exception:
    # When running the file directly (python agent_manager.py) the package context
    # may not be set; fall back to plain imports from the same directory.
    from precheck import TicketPrechecker
    from queryanalyser import analyse_query
    from solutionfinder import solution_finder
    from deterministic_evaluation import DeterministicEvaluator
    from response_composer import compose_response

import uuid
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from circuitbreaker import circuit

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

class AgentManager:
    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY not found in .env file")
        
        self.client = Mistral(api_key=self.api_key)
        self.prechecker = TicketPrechecker()
        self.evaluator = DeterministicEvaluator()
        self.model = "mistral-large-latest"
        self.confidence_threshold = 0.6
        
        # Mock Knowledge Base
        self.knowledge_base = [
            {"id": "kb1", "content": "Pour réinitialiser votre mot de passe, cliquez sur 'Mot de passe oublié' sur la page de connexion."},
            {"id": "kb2", "content": "Nos délais de livraison standard sont de 3 à 5 jours ouvrables."},
            {"id": "kb3", "content": "Le support technique est disponible de 9h à 18h, du lundi au vendredi."},
            {"id": "kb4", "content": "Vous pouvez retourner un article dans les 30 jours suivant l'achat s'il est dans son emballage d'origine."}
        ]

    def process_ticket(self, ticket_content):
        """
        Orchestrate the full ticket processing pipeline.
        """
        trace_id = str(uuid.uuid4())
        try:
            logger.info("Starting ticket processing", trace_id=trace_id, ticket_content=ticket_content[:100])
            print("\n" + "="*50)
            print("DÉBUT DU TRAITEMENT DU TICKET")
            print("="*50)

            # Step 1: Precheck
            print("\n[Étape 1] Pré-vérification...")
            precheck_results = self.prechecker.run_precheck(ticket_content)
            logger.info("Precheck completed", trace_id=trace_id, passed=precheck_results["passed"], reason=precheck_results.get("reason"))
            
            if not precheck_results["passed"]:
                print(f"❌ Échec de la pré-vérification : {', '.join(precheck_results['reason'])}")
                return {
                    "status": "rejected",
                    "reason": precheck_results["reason"],
                    "details": precheck_results
                }
            
            print("✅ Pré-vérification réussie.")

            # Step 1.1: Immediate Sensitive Data Check (Regex) - BEFORE any LLM call
            if self.evaluator._detect_sensitive_data(ticket_content):
                print(f"🚨 Données sensibles détectées dans la requête ! Escalade immédiate vers un agent humain...")
                escalation_msg = "Votre demande contient des informations sensibles (comme un numéro de carte ou des données personnelles). Pour votre sécurité, nous avons transmis votre dossier directement à un agent humain qui vous répondra par email sécurisé."
                print("\n" + "-"*30)
                print("RÉPONSE FINALE :")
                print(escalation_msg)
                print("-"*30)
                return {
                    "status": "escalated",
                    "reason": "Sensitive data detected in query (Regex)",
                    "final_response": escalation_msg,
                    "precheck": precheck_results,
                    "evaluation": {
                        "confidence_score": 0.0,
                        "sensitive_data": True,
                        "sentiment": "neutral",
                        "reason": "Sensitive data detected in query (Regex)"
                    }
                }

            # Use raw content for the AI agent (Masking moved to evaluation)
            content_to_process = ticket_content
            
            # Step 2: Query Analyser (LLM CALL)
            print("\n[Étape 2] Analyse de la requête...")
            analysis = analyse_query(content_to_process)
            # Safety: If the user mentions the product/company name, ensure it's in-scope
            if isinstance(content_to_process, str) and 'doxa' in content_to_process.lower():
                if not analysis.get('is_in_scope', True):
                    print("🔧 Override: 'doxa' mention detected — forcing is_in_scope=True")
                    analysis['is_in_scope'] = True
                    # If category is missing or set to 'Other', prefer 'Support and Reference Documentation'
                    if not analysis.get('category') or analysis.get('category') == 'Other':
                        analysis['category'] = 'Support and Reference Documentation'
            logger.info("Query analysis completed", trace_id=trace_id, summary=analysis.get("summary"), category=analysis.get("category"))
            print(f"📝 Résumé : {analysis.get('summary')}")
            print(f"Catégorie : {analysis.get('category')}")
            print(f"🔑 Mots-clés : {', '.join(analysis.get('keywords', []))}")
            
            # Check if the query is in scope for the company
            if not analysis.get("is_in_scope", True):
                print("🚫 Requête hors sujet (Hors périmètre Doxa).")
                out_of_scope_msg = "Désolé, je ne peux répondre qu'aux questions liées à Doxa et à nos services techniques. Votre demande semble être hors sujet."
                print("\n" + "-"*30)
                print("RÉPONSE FINALE :")
                print(out_of_scope_msg)
                print("-"*30)
                return {
                    "status": "rejected",
                    "reason": "Out of scope",
                    "final_response": out_of_scope_msg,
                    "analysis": analysis,
                    "precheck": precheck_results
                }

            # Optimization logic
            query_for_rag = content_to_process

            if not analysis.get("is_sufficient", True):
                print("⚠️ Requête jugée trop courte ou vague. Optimisation en cours...")
                query_for_rag = analysis.get("optimized_query", content_to_process)
                print(f"🔍 Requête optimisée : {query_for_rag}")
            else:
                # Even if sufficient, we can use the optimized version if it exists for better synonyms
                query_for_rag = analysis.get("optimized_query", content_to_process)

            # Step 3: Solution Finder (LLM CALL - RAG)
            print("\n[Étape 3] Recherche de solution (RAG)...")
            rag_result = solution_finder(query_for_rag, category=analysis.get("category"))
            logger.info("Solution finder completed", trace_id=trace_id, fallback_used=rag_result.get("fallback_used"), used_docs=len(rag_result["used_documents"]))
            
            if rag_result.get("fallback_used"):
                print("ℹ️ Note : La recherche a été étendue à d'autres catégories car aucun document pertinent n'a été trouvé dans la catégorie initiale.")

            proposed_answer = rag_result["answer"]
            print(f"💡 Solution proposée : {proposed_answer[:100]}...")
            
            # Get context used for evaluation
            context_used = "\n".join([doc["content"] for doc in rag_result["used_documents"]])
            # Get the best retrieval score (similarity)
            best_retrieval_score = rag_result["used_documents"][0].get("score", 0.5) if rag_result["used_documents"] else 0.0

            # Step 4: Deterministic Evaluation (Hugging Face model)
            print("\n[Étape 4] Évaluation de la confiance...")
            evaluation = self.evaluator.evaluate(
                query=query_for_rag,
                context=context_used,
                response=proposed_answer,
                retrieval_score=best_retrieval_score
            )
            logger.info("Evaluation completed", trace_id=trace_id, confidence_score=evaluation["confidence_score"], sensitive_data=evaluation.get("sensitive_data"))
            print(f"📊 Score de confiance global : {evaluation['confidence_score']}")
            print(f"   - Données sensibles détectées : {evaluation.get('sensitive_data', False)}")
            print(f"   - Raison de l'évaluation : {evaluation.get('reason', 'N/A')}")
            print(f"   - Sentiment détecté : {evaluation.get('sentiment', 'neutral')}")
            print(f"   - Non standard : {evaluation.get('non_standard', False)}")
            
            # Step 5 & 5.1: Logic based on confidence and safety
            # Escalation triggers: 
            # 1. Sensitive data detected (100% escalation)
            # 2. Confidence score < 0.6
            # 3. LLM refused to answer (no info found)
            # 4. User is angry
            
            should_escalate = (
                evaluation.get("sensitive_data", False) or 
                evaluation["confidence_score"] < self.confidence_threshold or
                evaluation.get("is_refusal", False) or
                evaluation.get("sentiment") == "angry"
            )

            if not should_escalate:
                print(f"✅ Confiance élevée et sécurité validée. Composition de la réponse finale...")
                # Step 5: Response Composer (LLM)
                final_response_data = compose_response(content_to_process, proposed_answer, evaluation)
                
                print("\n" + "-"*30)
                print("RÉPONSE FINALE :")
                print(final_response_data["final_response"])
                print("-"*30)

                return {
                    "status": "success",
                    "final_response": final_response_data["final_response"],
                    "confidence": evaluation["confidence_score"],
                    "analysis": analysis,
                    "precheck": precheck_results,
                    "proposed_answer": proposed_answer
                }
            else:
                # Step 5.1: Orient to specialist human agent (NO LLM)
                if evaluation.get("sensitive_data", False):
                    print(f"🚨 Données sensibles détectées ! Escalade immédiate vers un agent humain...")
                    reason = "Sensitive data detected (PII)"
                elif evaluation.get("sentiment") == "angry":
                    print(f"🚨 Utilisateur en colère ! Escalade immédiate vers un agent humain...")
                    reason = "User is angry"
                elif evaluation.get("is_refusal"):
                    print(f"⚠️ L'IA n'a pas trouvé de réponse dans les documents. Orientation vers un agent humain...")
                    reason = "No information found in KB"
                else:
                    print(f"⚠️ Confiance faible ({evaluation['confidence_score']}). Orientation vers un agent humain...")
                    reason = f"Low confidence score ({evaluation['confidence_score']})"
                
                result = self.orient_to_human(analysis, precheck_results)
                result["reason"] = reason
                print(f"👨‍💼 Orienté vers : {result['orientation']['target_department']}")
                return result

        except Exception as e:
            print(f"❌ Erreur critique lors du traitement : {e}")
            # In case of any unexpected error, escalate to human
            error_analysis = {"summary": "Error during processing", "agent_role": "agt_tech"}
            return self.orient_to_human(error_analysis, {"passed": True, "masked_content": ticket_content})

    def orient_to_human(self, analysis, precheck_results):
        """
        Orient the ticket to a specialist human agent using summary and keywords.
        """
        summary = analysis.get("summary", "N/A")
        keywords = analysis.get("keywords", [])
        agent_role = analysis.get("agent_role", "agt_tech") # Default to tech if not specified
        
        # Logic to "orient" could be more complex, but here we just return the info
        return {
            "status": "escalated",
            "reason": "Low confidence in AI response",
            "orientation": {
                "summary": summary,
                "keywords": keywords,
                "target_department": agent_role
            },
            "precheck": precheck_results
        }

    def handle_rating(self, ticket_id, stars, analysis, precheck_results):
        """
        Handle client rating. If <= 2 stars, escalate to human.
        """
        if stars <= 2:
            print(f"Rating low ({stars} stars). Escalating to human...")
            return self.orient_to_human(analysis, precheck_results)
        else:
            return {"status": "completed", "message": "Thank you for your feedback!"}

if __name__ == "__main__":
    from solutionfinder import ingest_pdf_to_chroma
    manager = AgentManager()
    
    while True:
        print("\n" + "-"*50)
        ticket = input("Veuillez saisir votre message (ou 'exit' pour quitter) : ")
        
        if ticket.lower() in ['exit', 'quit']:
            print("Fermeture du système. Au revoir !")
            break
            
        if ticket.startswith("/ingest "):
            # Improved parsing to handle spaces in category
            content = ticket.replace("/ingest ", "").strip()
            if content.startswith('"'):
                # Handle quoted path
                end_quote = content.find('"', 1)
                pdf_path = content[1:end_quote]
                category = content[end_quote+1:].strip() or "general"
            else:
                parts = content.split(" ", 1)
                pdf_path = parts[0]
                category = parts[1].strip() if len(parts) > 1 else "general"
            
            if os.path.exists(pdf_path):
                try:
                    ingest_pdf_to_chroma(pdf_path, category=category)
                except Exception as e:
                    print(f"❌ Erreur lors de l'ingestion : {e}")
            else:
                print(f"❌ Fichier introuvable : {pdf_path}")
            continue

        if not ticket.strip():
            continue
            
        try:
            result = manager.process_ticket(ticket)
            
            # Optionnel : Demander une évaluation si le traitement a réussi
            if result["status"] == "success":
                try:
                    print("\nComment évalueriez-vous cette réponse ? (1-5 étoiles)")
                    stars = input("Étoiles : ")
                    if stars.isdigit():
                        stars = int(stars)
                        rating_result = manager.handle_rating("ticket_id", stars, result["analysis"], result["precheck"])
                        if rating_result["status"] == "escalated":
                            print(f"\n⚠️ Suite à votre note, le ticket a été orienté vers : {rating_result['orientation']['target_department']}")
                        else:
                            print(f"\n✅ {rating_result['message']}")
                except Exception as e:
                    print(f"Erreur lors de l'évaluation : {e}")
        except Exception as e:
            logger.error("Unexpected error in pipeline", trace_id=trace_id, error=str(e), exc_info=True)
            print(f"\n❌ Une erreur inattendue est survenue : {e}")
            print("Veuillez vérifier votre connexion internet et réessayer.")
