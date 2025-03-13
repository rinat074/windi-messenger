import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';
import { SharedArray } from 'k6/data';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

// Метрики
const successfulMessages = new Counter('successful_messages');
const messageFailures = new Counter('message_failures');
const messageRate = new Rate('message_send_rate');
const messageResponseTime = new Trend('message_response_time');
const tokenRequestsRate = new Rate('token_requests_rate');
const websocketConnections = new Counter('websocket_connections');

// Параметры теста по умолчанию
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000/api/v1';

// Создание пользователей для тестирования 
// (предполагается, что они уже созданы в системе)
const testUsers = new SharedArray('users', function () {
  return [
    { email: 'user1@example.com', password: 'Password123!' },
    { email: 'user2@example.com', password: 'Password123!' },
    { email: 'user3@example.com', password: 'Password123!' },
    { email: 'user4@example.com', password: 'Password123!' },
    { email: 'user5@example.com', password: 'Password123!' },
  ];
});

// Настройки нагрузочного тестирования
export const options = {
  scenarios: {
    // Сценарий публикации сообщений через HTTP API
    publish_messages: {
      executor: 'ramping-arrival-rate',
      startRate: 5,
      timeUnit: '1s',
      preAllocatedVUs: 10,
      maxVUs: 50,
      stages: [
        { duration: '30s', target: 10 },  // Постепенно увеличиваем до 10 RPS
        { duration: '1m', target: 30 },   // Увеличиваем до 30 RPS за 1 минуту
        { duration: '2m', target: 30 },   // Держим 30 RPS в течение 2 минут
        { duration: '30s', target: 0 },   // Постепенно снижаем до 0
      ],
      exec: 'publishMessage',
    },
    
    // Сценарий получения токенов авторизации
    token_requests: {
      executor: 'constant-arrival-rate',
      rate: 5,
      timeUnit: '1s',
      duration: '4m',
      preAllocatedVUs: 5,
      maxVUs: 20,
      exec: 'getToken',
    }
  },
  thresholds: {
    'message_send_rate': ['rate>0.95'],                // 95% сообщений должны быть успешно отправлены
    'message_response_time': ['p(95)<500'],            // 95% ответов должны быть быстрее 500мс
    'token_requests_rate': ['rate>0.98'],              // 98% запросов токенов должны быть успешными
    'http_req_duration': ['p(95)<1000', 'p(99)<1500'], // Общая длительность запросов
  }
};

// Получение аутентификационного токена
function getAuthToken(userIndex = 0) {
  const user = testUsers[userIndex % testUsers.length];
  
  const loginResponse = http.post(`${BASE_URL}/users/login`, JSON.stringify({
    email: user.email,
    password: user.password
  }), {
    headers: { 'Content-Type': 'application/json' }
  });
  
  check(loginResponse, {
    'login successful': (r) => r.status === 200,
    'has access token': (r) => r.json('access_token') !== undefined,
  });
  
  if (loginResponse.status !== 200) {
    console.error(`Login failed for user ${user.email}: ${loginResponse.status} ${loginResponse.body}`);
    return null;
  }
  
  return loginResponse.json('access_token');
}

// Получение токена для подключения к Centrifugo
export function getToken() {
  const token = getAuthToken();
  if (!token) return;
  
  const centrifugoTokenResponse = http.post(`${BASE_URL}/centrifugo/token`, null, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  const success = check(centrifugoTokenResponse, {
    'centrifugo token request successful': (r) => r.status === 200,
    'has centrifugo token': (r) => r.json('token') !== undefined,
  });
  
  tokenRequestsRate.add(success);
  
  sleep(Math.random() * 3); // Случайная пауза до 3 секунд
}

// Публикация сообщения в канал
export function publishMessage() {
  const authToken = getAuthToken(Math.floor(Math.random() * testUsers.length));
  if (!authToken) return;
  
  // ID чата, в который публикуем сообщение
  // В реальном сценарии нужно получить список доступных чатов для пользователя
  const chatId = 1; // Пример статического ID чата
  
  const startTime = new Date();
  const publishResponse = http.post(
    `${BASE_URL}/centrifugo/publish?chat_id=${chatId}`,
    JSON.stringify({
      content: `Тестовое сообщение ${uuidv4()} - ${new Date().toISOString()}`,
      attachments: []
    }), 
    {
      headers: {
        'Authorization': `Bearer ${authToken}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  const duration = new Date() - startTime;
  messageResponseTime.add(duration);
  
  const success = check(publishResponse, {
    'publish successful': (r) => r.status === 200 || r.status === 201,
    'response has message id': (r) => r.json('id') !== undefined
  });
  
  if (success) {
    successfulMessages.add(1);
  } else {
    messageFailures.add(1);
    console.error(`Failed to publish message: ${publishResponse.status} ${publishResponse.body}`);
  }
  
  messageRate.add(success);
  
  // Случайная пауза между запросами до 2 секунд
  sleep(Math.random() * 2);
}

// Вспомогательная функция для создания тестового чата
export function setup() {
  console.log('Создание тестовых данных...');
  
  // Получаем токен первого пользователя
  const token = getAuthToken(0);
  if (!token) {
    console.error('Не удалось получить токен для создания тестового чата');
    return { chatId: 1 }; // Используем ID по умолчанию в случае ошибки
  }
  
  // Создаем тестовый чат
  const createChatResponse = http.post(
    `${BASE_URL}/chats`,
    JSON.stringify({
      name: `Тестовый чат ${new Date().toISOString()}`,
      is_private: false,
      participants: []  // Пустой массив - только создатель чата
    }),
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    }
  );
  
  if (createChatResponse.status === 200 || createChatResponse.status === 201) {
    const chatId = createChatResponse.json('id');
    console.log(`Создан тестовый чат с ID: ${chatId}`);
    return { chatId };
  } else {
    console.error(`Не удалось создать тестовый чат: ${createChatResponse.status} ${createChatResponse.body}`);
    return { chatId: 1 }; // Используем ID по умолчанию в случае ошибки
  }
}

// Функция завершения теста
export function teardown(data) {
  console.log(`Тест завершен. Использовался чат ID: ${data.chatId}`);
  // При необходимости можно удалить тестовые данные
}

/*
Для запуска теста установите k6 (https://k6.io/docs/getting-started/installation/) и выполните:

k6 run tests/performance/load_test_centrifugo.js

Для изменения параметров:

k6 run --env BASE_URL=http://example.com/api/v1 tests/performance/load_test_centrifugo.js
*/ 