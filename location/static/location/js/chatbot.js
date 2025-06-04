/**
 * ChatBot Manager - Version complète pour static/location/js/chatbot.js
 * Fonctionnalités :
 * - Connexion WebSocket sécurisée
 * - Reconnexion automatique
 * - Historique des messages
 * - Indicateur de saisie
 * - Protection XSS
 * - Gestion des suggestions
 */
class ChatBot {
  constructor(config) {
    // Configuration initiale
    this.config = config || {};
    this.socket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
    this.isTyping = false;
    this.messageQueue = [];
    
    // Initialisation
    this.initElements();
    this.initEventListeners();
    this.loadHistory();
    this.connectWebSocket();
  }

  initElements() {
    // Récupération des éléments DOM
    this.elements = {
      container: document.getElementById('chatbot-container'),
      form: document.getElementById('chat-form'),
      input: document.getElementById('chat-input'),
      messages: document.getElementById('chat-messages'),
      suggestions: document.getElementById('suggestions-container'),
      status: document.getElementById('connection-status'),
      statusText: document.querySelector('.status-text'),
      toggleBtn: document.getElementById('chatbot-toggle'),
      closeBtn: document.getElementById('chatbot-close')
    };
  }

  initEventListeners() {
    // Gestion des événements
    if (this.elements.form) {
      this.elements.form.addEventListener('submit', (e) => {
        e.preventDefault();
        this.handleUserInput();
      });
    }

    if (this.elements.input) {
      this.elements.input.addEventListener('input', () => this.handleTyping());
      this.elements.input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.handleUserInput();
        }
      });
    }

    if (this.elements.toggleBtn) {
      this.elements.toggleBtn.addEventListener('click', () => this.toggleChat());
    }

    if (this.elements.closeBtn) {
      this.elements.closeBtn.addEventListener('click', () => this.closeChat());
    }
  }

  connectWebSocket() {
    // Initialisation de la connexion WebSocket
    this.updateStatus('connecting');
    
    try {
      this.socket = new WebSocket(this.config.websocketUrl);

      this.socket.onopen = () => {
        this.reconnectAttempts = 0;
        this.updateStatus('connected');
        this.processQueue();
      };

      this.socket.onmessage = (e) => this.handleSocketMessage(e);
      this.socket.onclose = () => this.handleDisconnect();
      this.socket.onerror = (e) => this.handleError(e);
    } catch (e) {
      console.error('WebSocket init error:', e);
      this.handleError(e);
    }
  }

  handleSocketMessage(event) {
    // Traitement des messages entrants
    try {
      const data = JSON.parse(event.data);
      
      if (data.action === 'typing') {
        this.showTypingIndicator();
        return;
      }

      if (data.action === 'stop_typing') {
        this.hideTypingIndicator();
        return;
      }

      if (data.message) {
        this.displayMessage(data.message, 'bot');
        this.saveToHistory(data.message, 'bot');
      }

      if (data.suggestions) {
        this.showSuggestions(data.suggestions);
      }
    } catch (e) {
      console.error('Message processing error:', e);
      this.displayMessage("Erreur de traitement du message", 'error');
    }
  }

  handleUserInput() {
    // Gestion de la saisie utilisateur
    const message = this.elements.input.value.trim();
    if (!message) return;

    this.displayMessage(message, 'user');
    this.saveToHistory(message, 'user');
    this.sendToSocket({ message });
    this.elements.input.value = '';
    this.elements.input.focus();
  }

  handleTyping() {
    // Gestion de l'indicateur de saisie
    if (this.socket?.readyState === WebSocket.OPEN && !this.isTyping) {
      this.isTyping = true;
      this.sendToSocket({ action: 'typing' });
      
      setTimeout(() => {
        if (this.isTyping) {
          this.sendToSocket({ action: 'stop_typing' });
          this.isTyping = false;
        }
      }, 2000);
    }
  }

  sendToSocket(data) {
    // Envoi sécurisé via WebSocket
    const payload = {
      ...data,
      user_id: this.config.userId,
      csrf_token: this.config.csrfToken,
      timestamp: new Date().toISOString()
    };

    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(payload));
    } else {
      this.messageQueue.push(payload);
      this.handleDisconnect();
    }
  }

  processQueue() {
    // Traitement de la file d'attente
    while (this.messageQueue.length > 0 && this.socket?.readyState === WebSocket.OPEN) {
      const message = this.messageQueue.shift();
      this.socket.send(JSON.stringify(message));
    }
  }

  handleDisconnect() {
    // Gestion de la déconnexion
    this.updateStatus('disconnected');
    
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => {
        this.displayMessage(`Tentative de reconnexion (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'system');
        this.connectWebSocket();
      }, this.reconnectDelay);
    } else {
      this.displayMessage("Connexion perdue. Veuillez rafraîchir la page.", 'system');
    }
  }

  handleError(error) {
    // Gestion des erreurs
    console.error('ChatBot error:', error);
    this.updateStatus('error');
    this.displayMessage("Erreur de connexion au chatbot", 'error');
  }

  displayMessage(content, sender) {
    // Affichage des messages dans le chat
    if (!this.elements.messages) return;

    const messageEl = document.createElement('div');
    messageEl.className = `message ${sender}-message`;
    
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    messageEl.innerHTML = `
      <div class="message-content">${this.sanitize(content)}</div>
      <div class="message-meta">
        <span class="sender">${sender === 'user' ? 'Vous' : 'Assistant'}</span>
        <span class="time">${time}</span>
      </div>
    `;
    
    this.elements.messages.appendChild(messageEl);
    this.scrollToBottom();
  }

  showTypingIndicator() {
    // Affichage de l'indicateur de saisie
    if (!this.elements.messages) return;

    let indicator = document.getElementById('typing-indicator');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.id = 'typing-indicator';
      indicator.className = 'message bot typing';
      indicator.innerHTML = `
        <div class="message-content">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      `;
      this.elements.messages.appendChild(indicator);
      this.scrollToBottom();
    }
  }

  hideTypingIndicator() {
    // Masquage de l'indicateur de saisie
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
  }

  showSuggestions(suggestions) {
    // Affichage des suggestions
    if (!this.elements.suggestions || !suggestions?.length) return;

    this.elements.suggestions.innerHTML = suggestions
      .map(s => `<button class="suggestion-btn">${this.sanitize(s)}</button>`)
      .join('');

    // Ajout des écouteurs d'événements
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.elements.input.value = btn.textContent;
        this.handleUserInput();
        this.elements.suggestions.innerHTML = '';
      });
    });
  }

  updateStatus(status) {
    // Mise à jour du statut de connexion
    if (!this.elements.status || !this.elements.statusText) return;

    const statusMap = {
      connecting: { text: 'Connexion...', class: 'connecting' },
      connected: { text: 'Connecté', class: 'connected' },
      disconnected: { text: 'Déconnecté', class: 'disconnected' },
      error: { text: 'Erreur', class: 'error' }
    };

    const { text, class: className } = statusMap[status] || {};
    if (text && className) {
      this.elements.statusText.textContent = text;
      this.elements.status.className = `connection-status ${className}`;
    }
  }

  saveToHistory(content, sender) {
    // Sauvegarde dans l'historique
    const history = this.getHistory();
    history.push({
      content,
      sender,
      timestamp: new Date().toISOString()
    });
    localStorage.setItem('chatbotHistory', JSON.stringify(history));
  }

  loadHistory() {
    // Chargement de l'historique
    const history = this.getHistory();
    const recentMessages = history.slice(-10); // Limite à 10 messages
    
    recentMessages.forEach(msg => {
      this.displayMessage(msg.content, msg.sender);
    });
  }

  getHistory() {
    // Récupération de l'historique
    try {
      return JSON.parse(localStorage.getItem('chatbotHistory')) || [];
    } catch (e) {
      console.error('Error loading history:', e);
      return [];
    }
  }

  toggleChat() {
    // Basculer l'affichage du chat
    if (this.elements.container) {
      this.elements.container.classList.toggle('visible');
      this.elements.input.focus();
    }
  }

  closeChat() {
    // Fermer le chat
    if (this.elements.container) {
      this.elements.container.classList.remove('visible');
    }
  }

  scrollToBottom() {
    // Défilement vers le bas
    if (this.elements.messages) {
      this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }
  }

  sanitize(unsafe) {
    // Protection XSS
    return unsafe.toString()
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;")
      .replace(/\n/g, '<br>');
  }
}

// Initialisation lorsque le DOM est chargé
document.addEventListener('DOMContentLoaded', () => {
  if (typeof CHAT_CONFIG !== 'undefined') {
    try {
      new ChatBot(CHAT_CONFIG);
      console.log('ChatBot initialisé avec succès');
    } catch (e) {
      console.error('Erreur lors de l\'initialisation du ChatBot:', e);
    }
  } else {
    console.error('Configuration du chatbot non trouvée');
  }
});