/**
 * WinDI Messenger - пример клиента Centrifugo
 * 
 * Этот файл демонстрирует, как подключаться к Centrifugo
 * и обмениваться сообщениями в реальном времени.
 */

// Для работы примера необходимо установить библиотеку Centrifuge:
// npm install centrifuge

class WindiMessengerClient {
  constructor(apiUrl, wsUrl) {
    this.apiUrl = apiUrl || 'http://localhost:8000/api';
    this.wsUrl = wsUrl || 'ws://localhost:8001/connection/websocket';
    this.token = null;
    this.centrifuge = null;
    this.subscriptions = {};
    this.userId = null;
    this.username = null;
  }
  
  /**
   * Авторизация пользователя
   * @param {string} email - Email пользователя
   * @param {string} password - Пароль пользователя
   * @returns {Promise<string>} - JWT токен авторизации
   */
  async login(email, password) {
    try {
      const response = await fetch(`${this.apiUrl}/users/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email, password })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Ошибка аутентификации');
      }
      
      const data = await response.json();
      this.token = data.access_token;
      
      // Получаем информацию о текущем пользователе
      await this.fetchCurrentUser();
      
      return this.token;
    } catch (error) {
      console.error('Ошибка при входе:', error);
      throw error;
    }
  }
  
  /**
   * Получение информации о текущем пользователе
   */
  async fetchCurrentUser() {
    try {
      const response = await fetch(`${this.apiUrl}/users/me`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Не удалось получить информацию о пользователе');
      }
      
      const user = await response.json();
      this.userId = user.id;
      this.username = user.username;
      
      return user;
    } catch (error) {
      console.error('Ошибка при получении информации о пользователе:', error);
      throw error;
    }
  }
  
  /**
   * Получение токена для подключения к Centrifugo
   */
  async fetchCentrifugoToken() {
    try {
      const response = await fetch(`${this.apiUrl}/centrifugo/token`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      });
      
      if (!response.ok) {
        throw new Error('Не удалось получить токен Centrifugo');
      }
      
      const data = await response.json();
      return data.token;
    } catch (error) {
      console.error('Ошибка при получении токена Centrifugo:', error);
      throw error;
    }
  }
  
  /**
   * Подключение к серверу Centrifugo
   */
  async connect() {
    try {
      // Импортируем библиотеку Centrifuge
      const { Centrifuge } = await import('centrifuge');
      
      // Получаем токен для подключения к Centrifugo
      const centrifugoToken = await this.fetchCentrifugoToken();
      
      // Инициализируем соединение
      this.centrifuge = new Centrifuge(this.wsUrl);
      
      // Устанавливаем токен
      this.centrifuge.setToken(centrifugoToken);
      
      // Обработчики событий соединения
      this.centrifuge.on('connecting', context => {
        console.log('Подключение к Centrifugo...', context);
      });
      
      this.centrifuge.on('connected', context => {
        console.log('Подключено к Centrifugo!', context);
      });
      
      this.centrifuge.on('disconnected', context => {
        console.log('Отключено от Centrifugo', context);
      });
      
      // Подписываемся на персональный канал пользователя
      this.subscribeToUserChannel();
      
      // Подключаемся к серверу
      this.centrifuge.connect();
      
      return this.centrifuge;
    } catch (error) {
      console.error('Ошибка при подключении к Centrifugo:', error);
      throw error;
    }
  }
  
  /**
   * Подписка на персональный канал пользователя
   */
  subscribeToUserChannel() {
    if (!this.centrifuge) {
      throw new Error('Сначала необходимо подключиться к Centrifugo');
    }
    
    const userChannel = `user:${this.userId}`;
    const subscription = this.centrifuge.subscribe(userChannel);
    
    subscription.on('publication', data => {
      console.log('Получено уведомление в персональном канале:', data);
    });
    
    this.subscriptions[userChannel] = subscription;
    return subscription;
  }
  
  /**
   * Подписка на канал чата
   * @param {number} chatId - ID чата
   * @param {Function} onMessageCallback - Обработчик новых сообщений
   * @param {Function} onJoinCallback - Обработчик входа пользователей
   * @param {Function} onLeaveCallback - Обработчик выхода пользователей
   */
  subscribeToChat(chatId, onMessageCallback, onJoinCallback, onLeaveCallback) {
    if (!this.centrifuge) {
      throw new Error('Сначала необходимо подключиться к Centrifugo');
    }
    
    const chatChannel = `chat:${chatId}`;
    const subscription = this.centrifuge.subscribe(chatChannel);
    
    // Обработка новых сообщений
    subscription.on('publication', data => {
      console.log('Получено новое сообщение:', data);
      if (onMessageCallback) onMessageCallback(data);
    });
    
    // Обработка событий присоединения/ухода
    if (onJoinCallback) {
      subscription.on('join', ctx => {
        console.log('Пользователь присоединился:', ctx);
        onJoinCallback(ctx);
      });
    }
    
    if (onLeaveCallback) {
      subscription.on('leave', ctx => {
        console.log('Пользователь вышел:', ctx);
        onLeaveCallback(ctx);
      });
    }
    
    // Обработка ошибок подписки
    subscription.on('error', err => {
      console.error('Ошибка подписки на канал:', err);
    });
    
    this.subscriptions[chatChannel] = subscription;
    return subscription;
  }
  
  /**
   * Отправка сообщения в чат
   * @param {number} chatId - ID чата
   * @param {string} content - Текст сообщения
   * @param {Array} attachments - Массив вложений (опционально)
   */
  async sendMessage(chatId, content, attachments = []) {
    try {
      const response = await fetch(`${this.apiUrl}/centrifugo/publish?chat_id=${chatId}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content,
          attachments
        })
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Не удалось отправить сообщение');
      }
      
      return await response.json();
    } catch (error) {
      console.error('Ошибка при отправке сообщения:', error);
      throw error;
    }
  }
  
  /**
   * Получение списка пользователей, находящихся в чате
   * @param {number} chatId - ID чата
   * @returns {Promise<Object>} - Данные о присутствии
   */
  async getChatPresence(chatId) {
    try {
      const response = await fetch(`${this.apiUrl}/centrifugo/presence/${chatId}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${this.token}`
        }
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Не удалось получить данные о присутствии');
      }
      
      return await response.json();
    } catch (error) {
      console.error('Ошибка при получении данных о присутствии:', error);
      throw error;
    }
  }
  
  /**
   * Отключение от сервера
   */
  disconnect() {
    if (this.centrifuge) {
      this.centrifuge.disconnect();
      this.subscriptions = {};
    }
  }
}

// Пример использования клиента
async function exampleUsage() {
  const client = new WindiMessengerClient();
  
  try {
    // Вход в систему
    await client.login('user@example.com', 'password123');
    console.log('Успешный вход!');
    
    // Подключение к Centrifugo
    await client.connect();
    
    // Подписка на чат
    client.subscribeToChat(1, 
      // Обработчик новых сообщений
      message => {
        console.log(`Новое сообщение от ${message.sender_name}: ${message.content}`);
        
        // Пример ответа на сообщение
        if (message.sender_id !== client.userId) {
          setTimeout(() => {
            client.sendMessage(1, `Ответ на сообщение: ${message.content}`);
          }, 1000);
        }
      },
      // Обработчик входа пользователей
      join => {
        console.log(`Пользователь ${join.info.name} присоединился к чату`);
      },
      // Обработчик выхода пользователей
      leave => {
        console.log(`Пользователь ${leave.info.name} вышел из чата`);
      }
    );
    
    // Отправка сообщения
    await client.sendMessage(1, 'Привет, это тестовое сообщение!');
    
    // Получение информации о пользователях в чате
    const presence = await client.getChatPresence(1);
    console.log('Пользователи в чате:', presence);
    
  } catch (error) {
    console.error('Ошибка в примере использования:', error);
  }
}

// Раскомментируйте, чтобы запустить пример:
// exampleUsage(); 