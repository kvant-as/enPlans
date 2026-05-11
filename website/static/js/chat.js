const ChatModule = (function () {
  let _state = {
    currentChatId: null,
    currentChatType: null,
    currentUserId: 1,
    messageCheckInterval: null,
    selectedTypeText: null,
    lastMessageCount: 0,
    isSending: false,
    pendingMessages: [],
    processedMessageIds: new Set(),
    isLoading: false,
  };

    function _showSendingIndicator() {
        const sendBtn = document.querySelector(".chat-btn");
        if (!sendBtn) return;

        if (!sendBtn.dataset.originalHtml) {
            sendBtn.dataset.originalHtml = sendBtn.innerHTML;
        }
        
        const btnWidth = sendBtn.offsetWidth;
        const btnHeight = sendBtn.offsetHeight;
        
        sendBtn.innerHTML = '<div class="sending-indicator"></div>';
        sendBtn.disabled = true;
        
        if (btnWidth > 32) {
            sendBtn.style.width = btnWidth + 'px';
        }
    }

  function _hideSendingIndicator() {
    const sendBtn = document.querySelector(".chat-btn");
    if (!sendBtn) return;
    if (sendBtn.dataset.originalHtml) {
      sendBtn.innerHTML = sendBtn.dataset.originalHtml;
      delete sendBtn.dataset.originalHtml;
    }
    sendBtn.disabled = false;
  }

  function _showTypingIndicator() {
    if (_state.isTyping) return;

    _removeTypingIndicator();

    const container = document.getElementById("messagesList");
    if (!container) return;

    const typingDiv = document.createElement("div");
    typingDiv.className = "message bot typing-indicator-container";
    typingDiv.id = "typingIndicator";

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "👩‍💻";

    const contentDiv = document.createElement("div");
    contentDiv.className = "chat-message-content";

    const typingIndicator = document.createElement("div");
    typingIndicator.className = "typing-indicator";
    typingIndicator.innerHTML = "<span></span><span></span><span></span>";

    contentDiv.appendChild(typingIndicator);
    typingDiv.appendChild(avatar);
    typingDiv.appendChild(contentDiv);

    container.appendChild(typingDiv);
    _scrollToBottom();
  }

  function _removeTypingIndicator() {
    const indicator = document.getElementById("typingIndicator");
    if (indicator) indicator.remove();
  }

  async function _typeWriterEffect(element, text, speed = 30) {
    if (_state.isTyping) return;

    _state.isTyping = true;
    element.innerHTML = "";

    const chars = text.split("");
    let currentHtml = "";

    for (let i = 0; i < chars.length; i++) {
      if (!_state.isTyping) break;

      currentHtml += chars[i];
      element.innerHTML = currentHtml;
      _scrollToBottom();

      await _delay(speed);
    }

    element.innerHTML = text;
    _state.isTyping = false;
    _scrollToBottom();
  }

  function _delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  function _showPage(pageId) {
    document.querySelectorAll(".chat-page").forEach((page) => {
      page.classList.remove("active");
    });

    const page = document.getElementById(pageId);
    if (page) page.classList.add("active");

    const chatInputArea = document.getElementById("chatInputArea");
    if (pageId === "pageActiveChat") {
      chatInputArea.style.display = "flex";
      document.getElementById("messageInput").focus();
      setTimeout(_scrollToBottom, 100);
    } else {
      chatInputArea.style.display = "none";
      _removeEndChatButton();
    }
  }

  async function _checkExistingChatAndOpen() {
    try {
      const response = await fetch("/api/chat/check-existing-chat");
      const data = await response.json();

      if (data.has_active_chat) {
        _state.currentChatId = data.chat_id;
        _state.currentChatType = data.chat_type;

        await _loadExistingMessages();

        _showPage("pageActiveChat");
        _startMessageCheck();
        _scrollToBottom();
      } else {
        _showPage("pageChatType");
      }
    } catch (error) {
      console.error("Error checking existing chat:", error);
      _showPage("pageChatType");
    }
  }

  async function _loadExistingMessages() {
    if (!_state.currentChatId || _state.isLoading) return;

    _state.isLoading = true;

    try {
      const response = await fetch(
        `/api/chat/${_state.currentChatId}/messages`,
      );
      const messages = await response.json();

      const messagesList = document.getElementById("messagesList");
      messagesList.innerHTML = "";
      _state.processedMessageIds.clear();

      messages.forEach((msg) => {
        _addMessageToUI(msg, msg.is_user);
        _state.processedMessageIds.add(msg.id);
      });

      _state.lastMessageCount = messages.length;
      if (!_state.selectedTypeText && messages.length > 0) {
        _state.selectedTypeText = _state.selectedTypeText || "Наименование темы";
      }

      _updateWelcomeMessageForExistingChat(messages.length > 0);

      if (messages.length > 0) {
        _addEndChatButton();
      }
    } catch (error) {
      console.error("Error loading existing messages:", error);
    } finally {
      _state.isLoading = false;
    }
  }
  function _updateWelcomeMessageForExistingChat(hasMessages) {
    const welcomeMessage = document.querySelector(
      "#pageActiveChat .welcome-message .message-text",
    );
    const welcomeContainer = document.querySelector(
      "#pageActiveChat .welcome-message",
    );

    if (!welcomeMessage || !welcomeContainer) return;

    welcomeContainer.style.display = "block";

    if (hasMessages) {
      welcomeMessage.innerHTML = `Добрый день! <br>Вы выбрали <strong>${_state.selectedTypeText || "тему"}</strong>, какой вопрос у вас возник?`;
    } else {
      welcomeMessage.innerHTML = `Добрый день! <br>Вы выбрали <strong>${_state.selectedTypeText || "тему"}</strong>, какой вопрос у вас возник?`;
    }
  }

  async function _handleChatTypeSelection(type) {
    _state.currentChatType = type;

    const typeTexts = {
      "no-org": "Нет организации",
      "compl-plan": "Заполнение плана",
      dif: "Другое",
    };

    _state.selectedTypeText = typeTexts[type];

    await _welcomeInChat(true, _state.selectedTypeText);
    _showPage("pageActiveChat");
    _addBackButton();
  }

  async function _welcomeInChat(is_full, type) {
    const welcomeMessage = document.querySelector(
      "#pageActiveChat .welcome-message .message-text",
    );
    const welcomeContainer = document.querySelector(
      "#pageActiveChat .welcome-message",
    );

    if (welcomeMessage && welcomeContainer) {
      welcomeContainer.style.display = "block";

      let message = `Добрый день! <br>Вы выбрали <strong>${_state.selectedTypeText}</strong>, какой вопрос у вас возник?`;

      if (is_full) {
        message += ` <br><br>Для смены темы нажмите <strong>Назад к выбору тем</strong>, для продолжения напишите ваш вопрос.`;
      }
      welcomeMessage.innerHTML = message;
    }
  }

  async function _sendMessage() {
      const input = document.getElementById("messageInput");
      const content = input.value.trim();

      if (!content) {
          input.classList.add('error');
          input.focus();
          return;
      }

      if (_state.isSending) return;

      _state.isSending = true;
      _showSendingIndicator();

      _removeBackButton();

      const tempId = "temp_" + Date.now() + "_" + Math.random().toString(36).substr(2, 9);

      const userMessage = {
          id: tempId,
          content: content,
          sender_id: _state.currentUserId,
          is_user: true,
          created_at: new Date().toISOString(),
          temp: true,
      };

      _addMessageToUI(userMessage, true);
      _state.pendingMessages.push(tempId);

      input.value = "";

      _showTypingIndicator();

      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;

      try {
          const response = await fetch("/api/chat/send-message", {
              method: "POST",
              headers: {
                  "Content-Type": "application/json",
                  ...(csrfToken && { "X-CSRFToken": csrfToken }),
              },
              body: JSON.stringify({
                  content: content,
                  sender_id: _state.currentUserId,
                  chat_type: _state.currentChatType,
              }),
          });

          const data = await response.json();

          if (!response.ok || !data.success) {
              _removeTypingIndicator();
              
              let errorMessage = "Извините, произошла ошибка. Попробуйте позже.";
              
              if (response.status === 403) {
                  errorMessage = "🔒 Чат поддержки доступен только для администраторов. Пожалуйста, войдите в систему как администратор.";
              } else if (data.error) {
                  errorMessage = data.error;
              }
              
              // Добавляем сообщение об ошибке как обычное сообщение бота
              const botMessage = {
                  id: "error_" + Date.now(),
                  content: errorMessage,
                  sender_id: null,
                  is_user: false,
                  created_at: new Date().toISOString()
              };
              
              _addMessageToUI(botMessage, false);
              _scrollToBottom();
              
              return;
          }

          if (data.success) {
              _state.currentChatId = data.chat_id;
              _startMessageCheck();

              const tempMessageElement = document.querySelector(`[data-message-id="${tempId}"]`);
              if (tempMessageElement) {
                  tempMessageElement.dataset.messageId = data.message_id;
                  tempMessageElement.classList.remove("temp-message");
                  _state.processedMessageIds.add(data.message_id);
              }

              _state.pendingMessages = _state.pendingMessages.filter((id) => id !== tempId);
          }
          _addEndChatButton();
      } catch (error) {
          console.error("Error sending message:", error);
          _removeTypingIndicator();
          
          // Удаляем временное сообщение пользователя при ошибке
          const tempMessageElement = document.querySelector(`[data-message-id="${tempId}"]`);
          if (tempMessageElement) {
              tempMessageElement.remove();
          }
          
          // Добавляем сообщение об ошибке как обычное сообщение бота
          const botMessage = {
              id: "error_" + Date.now(),
              content: "❌ Не удалось отправить сообщение. Проверьте подключение к интернету и попробуйте снова.",
              sender_id: null,
              is_user: false,
              created_at: new Date().toISOString()
          };
          
          _addMessageToUI(botMessage, false);
          _scrollToBottom();
      } finally {
          _hideSendingIndicator();
          _state.isSending = false;
      }
  }

  function _addMessageToUI(message, isSent, containerId = "messagesList") {
    const container = document.getElementById(containerId);
    if (!container) return;

    const existingMsg = document.querySelector(
      `[data-message-id="${message.id}"]`,
    );
    if (existingMsg) return;

    if (!message.temp && _state.processedMessageIds.has(message.id)) {
      return;
    }

    const messageDiv = document.createElement("div");
    messageDiv.className = `message ${isSent ? "user" : "bot"}`;
    messageDiv.dataset.messageId = message.id;

    if (message.temp) {
      messageDiv.classList.add("temp-message");
    }

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = isSent ? "👤" : "👩‍💻";

    const contentDiv = document.createElement("div");
    contentDiv.className = "chat-message-content";

    const textDiv = document.createElement("div");
    textDiv.className = "message-text";
    textDiv.textContent = message.content;
    contentDiv.appendChild(textDiv);

    if (message.created_at) {
      const timeDiv = document.createElement("div");
      timeDiv.className = "message-time";
      const date = new Date(message.created_at);
      timeDiv.textContent = date.toLocaleTimeString("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
      });
      contentDiv.appendChild(timeDiv);
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    container.appendChild(messageDiv);

    if (!message.temp) {
      _state.processedMessageIds.add(message.id);
    }

    _scrollToBottom();
  }

  function _addBackButton() {
    const existingBtn = document.querySelector(".back-to-type-btn");
    if (existingBtn) existingBtn.remove();

    const chatPage = document.getElementById("pageActiveChat");
    if (!chatPage) return;

    const backBtn = document.createElement("button");
    backBtn.className = "back-to-type-btn";
    backBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M19 12H5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <path d="M12 19L5 12L12 5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span>Назад к выбору темы</span>
        `;
    backBtn.onclick = function () {
      _showPage("pageChatType");
      this.remove();
    };
    chatPage.appendChild(backBtn);
  }

  function _removeBackButton() {
    const backBtn = document.querySelector(".back-to-type-btn");
    if (backBtn) backBtn.remove();
  }

  function _addEndChatButton() {
    const existingBtn = document.querySelector(".chat-btn-back");
    if (existingBtn) existingBtn.remove();

    const chatContainer = document.getElementById("delchatarrea");
    if (!chatContainer) return;

    const endChatBtn = document.createElement("button");
    endChatBtn.className = "chat-btn-back";
    endChatBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                <path d="M6 6L18 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span>Завершить чат</span>
        `;
    endChatBtn.onclick = _endChat;
    chatContainer.appendChild(endChatBtn);
  }

  function _removeEndChatButton() {
    const endChatBtn = document.querySelector(".chat-btn-back");
    if (endChatBtn) endChatBtn.remove();
  }

  async function _endChat() {
    if (!_state.currentChatId) return;

    _state.isTyping = false;
    _state.isSending = true;
    _showSendingIndicator();

    const csrfToken = document.querySelector(
      'meta[name="csrf-token"]',
    )?.content;

    try {
      const response = await fetch(`/api/chat/${_state.currentChatId}/end`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(csrfToken && { "X-CSRFToken": csrfToken }),
        },
      });

      if (response.ok) {
        await _delay(2000);
        _stopMessageCheck();

        _state.currentChatId = null;
        _state.currentChatType = null;
        _state.pendingMessages = [];
        _state.isTyping = false;
        _state.processedMessageIds.clear();

        _resetChat();
        _showPage("pageChatType");
      }
    } catch (error) {
      console.error("Error ending chat:", error);
    } finally {
      _hideSendingIndicator();
      _state.isSending = false;
    }
  }

  function _startMessageCheck() {
    _stopMessageCheck();
    _state.messageCheckInterval = setInterval(_checkNewMessages, 3000);
  }

  function _stopMessageCheck() {
    if (_state.messageCheckInterval) {
      clearInterval(_state.messageCheckInterval);
      _state.messageCheckInterval = null;
    }
  }

    async function _checkNewMessages() {
        // Добавляем проверку на currentChatId
        if (!_state.currentChatId || _state.isTyping || _state.isLoading) {
        return;
        }

        try {
        const response = await fetch(
            `/api/chat/${_state.currentChatId}/messages`,
        );
        const messages = await response.json();

        const botMessages = messages.filter(
            (msg) =>
            !_state.processedMessageIds.has(msg.id) &&
            msg.sender_id !== _state.currentUserId,
        );

        messages.forEach((msg) => {
            if (msg.sender_id === _state.currentUserId) {
            _state.processedMessageIds.add(msg.id);
            }
        });

        if (botMessages.length > 0) {
            _removeTypingIndicator();

            const lastBotMessage = botMessages[botMessages.length - 1];
            await _addBotMessageWithTyping(lastBotMessage);

            botMessages.forEach((msg) => {
            _state.processedMessageIds.add(msg.id);
            });

            _state.lastMessageCount = messages.length;
        }
        } catch (error) {
        console.error("Error checking new messages:", error);
        }
    }

  async function _addBotMessageWithTyping(message) {
    if (_state.processedMessageIds.has(message.id)) return;

    const container = document.getElementById("messagesList");
    if (!container) return;

    const messageDiv = document.createElement("div");
    messageDiv.className = "message bot";
    messageDiv.dataset.messageId = message.id;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = "👩‍💻";

    const contentDiv = document.createElement("div");
    contentDiv.className = "chat-message-content";

    const textDiv = document.createElement("div");
    textDiv.className = "message-text";

    contentDiv.appendChild(textDiv);

    if (message.created_at) {
      const timeDiv = document.createElement("div");
      timeDiv.className = "message-time";
      const date = new Date(message.created_at);
      timeDiv.textContent = date.toLocaleTimeString("ru-RU", {
        hour: "2-digit",
        minute: "2-digit",
      });
      contentDiv.appendChild(timeDiv);
    }

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    container.appendChild(messageDiv);

    await _typeWriterEffect(textDiv, message.content, 40);
    _state.processedMessageIds.add(message.id);
  }

  function _resetChat() {
    _stopMessageCheck();

    _state.currentChatId = null;
    _state.currentChatType = null;
    _state.selectedTypeText = null;
    _state.lastMessageCount = 0;
    _state.pendingMessages = [];
    _state.isTyping = false;
    _state.isLoading = false;
    _state.processedMessageIds.clear();

    const messagesList = document.getElementById("messagesList");
    if (messagesList) messagesList.innerHTML = "";

    const messageInput = document.getElementById("messageInput");
    if (messageInput) {
      messageInput.disabled = false;
      messageInput.value = "";
    }

    _removeTypingIndicator();
    _removeEndChatButton();

    const welcomeContainer = document.querySelector(
      "#pageActiveChat .welcome-message",
    );
    if (welcomeContainer) {
      welcomeContainer.style.display = "block";
    }
  }

  function _scrollToBottom() {
    const messagesContainer = document.getElementById("chatMessages");
    if (!messagesContainer) return;

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }



return {
    init: async function (userId) {
      if (userId) _state.currentUserId = userId;
    },

    toggleChat: function () {
      const container = document.getElementById("chatContainer");
      container.classList.toggle("active");

      if (container.classList.contains("active")) {
        const toggleBtn = document.querySelector(".chat-toggle");
        if (toggleBtn) toggleBtn.style.display = "none";
        _resetChat();
        _checkExistingChatAndOpen();
        _initTextarea();
      } else {
        const toggleBtn = document.querySelector(".chat-toggle");
        if (toggleBtn) toggleBtn.style.display = "flex";
      }
    },

    selectChatType: _handleChatTypeSelection,
    sendMessage: _sendMessage,
    endChat: _endChat,

    handleKeyDown: function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        _sendMessage();
      }
    },

    setUserId: function (userId) {
      _state.currentUserId = userId;
    },
  };
})();

window.ChatModule = ChatModule;

(function makeChatDraggable() {
    const chatContainer = document.getElementById('chatContainer');
    const chatHeader = document.querySelector('.chat-header-info');
    
    if (!chatContainer || !chatHeader) return;
    
    let isDragging = false;
    let offsetX, offsetY;
    
    chatHeader.addEventListener('mousedown', (e) => {
        isDragging = true;
        
        // Вычисляем смещение от левого верхнего угла контейнера до места клика
        const rect = chatContainer.getBoundingClientRect();
        offsetX = e.clientX - rect.left;
        offsetY = e.clientY - rect.top;
        
        chatContainer.style.cursor = 'grabbing';
        chatContainer.style.transition = 'none';
    });
    
    document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        
        e.preventDefault();
        
        // Новая позиция с учетом смещения
        const newLeft = e.clientX - offsetX;
        const newTop = e.clientY - offsetY;
        
        // Ограничиваем перемещение в пределах окна
        const maxLeft = window.innerWidth - chatContainer.offsetWidth;
        const maxTop = window.innerHeight - chatContainer.offsetHeight;
        
        chatContainer.style.left = Math.max(0, Math.min(newLeft, maxLeft)) + 'px';
        chatContainer.style.top = Math.max(0, Math.min(newTop, maxTop)) + 'px';
        chatContainer.style.bottom = 'auto';
        chatContainer.style.right = 'auto';
    });
    
    document.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            chatContainer.style.cursor = '';
            chatContainer.style.transition = '';
        }
    });
})();