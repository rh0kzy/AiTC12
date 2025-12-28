import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Bot, User, Loader2, Sparkles, ShieldAlert, BadgeCheck } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const [messages, setMessages] = useState([
    { role: 'ai', content: 'Bonjour ! Je suis l\'assistant intelligent de Doxa. Comment puis-je vous aider aujourd\'hui ?' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/process_ticket`, {
        ticket: input
      });

      const data = response.data;
      let aiResponseContent = '';
      let status = data.status;

      if (status === 'success') {
        aiResponseContent = data.final_response;
      } else if (status === 'escalated') {
        aiResponseContent = data.final_response || `Votre demande a été transmise à un agent humain (${data.orientation?.target_department || 'Support'}). Raison : ${data.reason}`;
      } else if (status === 'rejected') {
        aiResponseContent = data.final_response || `Désolé, votre demande a été rejetée. Raison : ${data.reason}`;
      }

      setMessages(prev => [...prev, {
        role: 'ai',
        content: aiResponseContent,
        status: status,
        details: data
      }]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        role: 'ai',
        content: 'Désolé, une erreur technique est survenue. Veuillez vérifier que le serveur backend est en cours d\'exécution.',
        status: 'error'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <header style={{ marginBottom: '2rem', textAlign: 'center' }}>
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5 }}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem' }}
        >
          <div style={{ background: 'var(--primary-color)', padding: '0.5rem', borderRadius: '0.75rem' }}>
            <Sparkles size={32} color="white" />
          </div>
          <h1 style={{ margin: 0, fontSize: '2rem', fontWeight: 800, letterSpacing: '-0.025em' }}>
            Doxa AI <span style={{ color: 'var(--primary-color)' }}>Agent</span>
          </h1>
        </motion.div>
        <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>Système de Support Intelligent & RAG</p>
      </header>

      <main className="glass-morphism messages-list" style={{ flex: 1, padding: '1.5rem' }}>
        <AnimatePresence>
          {messages.map((msg, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, x: msg.role === 'user' ? 20 : -20 }}
              animate={{ opacity: 1, x: 0 }}
              className={`message message-${msg.role}`}
              style={{
                display: 'flex',
                gap: '1rem',
                position: 'relative'
              }}
            >
              <div style={{
                minWidth: '32px',
                height: '32px',
                borderRadius: '50%',
                background: msg.role === 'ai' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                {msg.role === 'ai' ? <Bot size={18} /> : <User size={18} />}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.9rem', marginBottom: '0.25rem', opacity: 0.7 }}>
                  {msg.role === 'ai' ? 'Assistant Doxa' : 'Vous'}
                  {msg.status === 'success' && <BadgeCheck size={14} style={{ marginLeft: '4px', display: 'inline', color: '#10b981' }} />}
                  {msg.status === 'escalated' && <ShieldAlert size={14} style={{ marginLeft: '4px', display: 'inline', color: '#f59e0b' }} />}
                </div>
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                {msg.details && msg.details.confidence && (
                  <div style={{ fontSize: '0.75rem', marginTop: '0.5rem', opacity: 0.5 }}>
                    Confiance: {(msg.details.confidence * 100).toFixed(0)}%
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {isLoading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="message message-ai"
            style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}
          >
            <Loader2 className="animate-spin" size={18} />
            <span>L'agent réfléchit...</span>
          </motion.div>
        )}
        <div ref={messagesEndRef} />
      </main>

      <footer className="input-area">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Posez votre question à Doxa..."
          disabled={isLoading}
        />
        <button onClick={handleSend} disabled={isLoading || !input.trim()}>
          {isLoading ? <Loader2 className="animate-spin" size={20} /> : <Send size={20} />}
          Envoyer
        </button>
      </footer>
    </div>
  );
}

export default App;
