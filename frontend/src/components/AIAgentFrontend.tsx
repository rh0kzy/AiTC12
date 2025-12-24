import React, { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Loader2, Settings, Trash2, Download } from 'lucide-react'

export default function AIAgentFrontend() {
  const [messages, setMessages] = useState<any[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  // Use Vite proxy: '/api/process_ticket' -> backend '/process_ticket'
  const [apiUrl, setApiUrl] = useState('/api/process_ticket')
  const [showSettings, setShowSettings] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Remove leading numbering like "1.", "2)" at the start of lines in assistant responses
  const sanitizeResponse = (text: string) => {
    if (!text) return text
    // Remove numeric list markers at start of any line: "1. ", "2) ", "3 - ", etc.
    const cleaned = text.replace(/^\s*\d+[\.\)\-]\s+/gm, '')
    // Also collapse multiple blank lines
    return cleaned.replace(/\n{3,}/g, '\n\n').trim()
  }

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // Backend expects `{ ticket: string }`
        body: JSON.stringify({ ticket: input })
      })

      // 202: manager starting
      if (response.status === 202) {
        const data = await response.json()
        const assistantMessage = {
          id: Date.now() + 1,
          role: 'assistant',
          content: sanitizeResponse(data.message || 'Le backend démarre, réessayez dans quelques instants.'),
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, assistantMessage])
      } else if (response.ok) {
        const data = await response.json()
        // Handle backend structure from Flask: success | escalated | rejected
        let text = ''
        if (data.status === 'success') {
          text = data.final_response || data.proposed_answer || data.answer || JSON.stringify(data)
        } else if (data.status === 'escalated') {
          const dept = data.orientation?.target_department || data.orientation?.target || data.reason || 'agent humain'
          const msg = data.final_response || data.proposed_answer || ''
          text = `Orienté vers: ${dept}. ${msg}`
        } else if (data.status === 'rejected') {
          text = data.reason || data.final_response || 'Requête rejetée par le backend.'
        } else {
          text = JSON.stringify(data)
        }

        const assistantMessage = {
          id: Date.now() + 1,
          role: 'assistant',
          content: sanitizeResponse(text),
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, assistantMessage])
      } else {
        const body = await response.text()
        throw new Error(`Erreur HTTP: ${response.status} - ${body}`)
      }
    } catch (error: any) {
      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: sanitizeResponse(`Erreur: ${error.message}. Vérifiez que votre backend est démarré et que l'URL API est correcte.`),
        timestamp: new Date().toISOString(),
        isError: true
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const clearChat = () => {
    if (confirm('Voulez-vous vraiment effacer toute la conversation ?')) {
      setMessages([])
    }
  }

  const exportChat = () => {
    const chatData = JSON.stringify(messages, null, 2)
    const blob = new Blob([chatData], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `conversation-${new Date().toISOString()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <div className="bg-slate-800/50 backdrop-blur-lg border-b border-slate-700/50 p-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-br from-purple-500 to-pink-500 p-2 rounded-lg">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">AI Agent</h1>
              <p className="text-xs text-slate-400">Assistant intelligent</p>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={exportChat}
              className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
              title="Exporter la conversation"
            >
              <Download className="w-5 h-5 text-slate-300" />
            </button>
            <button
              onClick={clearChat}
              className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
              title="Effacer la conversation"
            >
              <Trash2 className="w-5 h-5 text-slate-300" />
            </button>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 hover:bg-slate-700/50 rounded-lg transition-colors"
              title="Paramètres"
            >
              <Settings className="w-5 h-5 text-slate-300" />
            </button>
          </div>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="bg-slate-800/90 backdrop-blur-lg border-b border-slate-700/50 p-4">
          <div className="max-w-4xl mx-auto">
            <label className="block text-sm font-medium text-slate-300 mb-2">
              URL de l'API Backend
            </label>
            <input
              type="text"
              value={apiUrl}
              onChange={(e) => setApiUrl(e.target.value)}
              className="w-full px-4 py-2 bg-slate-900/50 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500"
              placeholder="http://localhost:3000/api/chat"
            />
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <Bot className="w-16 h-16 text-purple-400 mx-auto mb-4 opacity-50" />
              <h2 className="text-2xl font-bold text-white mb-2">
                Bienvenue sur AI Agent
              </h2>
              <p className="text-slate-400">
                Commencez une conversation avec votre assistant IA
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="bg-gradient-to-br from-purple-500 to-pink-500 p-2 rounded-lg h-fit">
                  <Bot className="w-5 h-5 text-white" />
                </div>
              )}

              <div
                className={`max-w-2xl rounded-2xl px-4 py-3 ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-br from-purple-600 to-purple-700 text-white'
                    : msg.isError
                    ? 'bg-red-900/50 border border-red-700 text-red-200'
                    : 'bg-slate-800/80 backdrop-blur-sm border border-slate-700 text-slate-100'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                <span className="text-xs opacity-60 mt-1 block">
                  {new Date(msg.timestamp).toLocaleTimeString('fr-FR')}
                </span>
              </div>

              {msg.role === 'user' && (
                <div className="bg-gradient-to-br from-blue-500 to-cyan-500 p-2 rounded-lg h-fit">
                  <User className="w-5 h-5 text-white" />
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3 justify-start">
              <div className="bg-gradient-to-br from-purple-500 to-pink-500 p-2 rounded-lg h-fit">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="bg-slate-800/80 backdrop-blur-sm border border-slate-700 rounded-2xl px-4 py-3">
                <div className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />
                  <span className="text-slate-300">En train de réfléchir...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="bg-slate-800/50 backdrop-blur-lg border-t border-slate-700/50 p-4">
        <form onSubmit={sendMessage} className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Tapez votre message..."
              className="flex-1 px-4 py-3 bg-slate-900/50 border border-slate-600 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-xl font-medium hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
              Envoyer
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
