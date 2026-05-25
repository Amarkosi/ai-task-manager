import { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [tasks, setTasks] = useState([]);

  // Вытаскиваем user_id из URL параметров
  const urlParams = new URLSearchParams(window.location.search);
  const userId = urlParams.get('user_id');

  # Используем адрес из переменных окружения Vite (или локальный по умолчанию для Docker/разработки)
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  # Формируем безопасный WebSocket URL (меняем http на ws)
  const WS_BASE = API_BASE.replace(/^http/, 'ws');

  // 1. Функция первоначальной загрузки задач через HTTP
  const fetchTasks = async () => {
    try {
      const config = userId ? { params: { user_id: userId } } : {};
      const response = await axios.get(`${API_BASE}/tasks`, config);
      setTasks(response.data);
    } catch (error) {
      console.error("Ошибка при получении задач:", error);
    }
  };

  // 2. Функция обновления статуса задачи при клике на кнопки
  const updateStatus = async (taskId, newStatus) => {
    try {
      await axios.patch(`${API_BASE}/tasks/${taskId}`, { status: newStatus });
      // ВАЖНО:fetchTasks() больше вызывать не нужно! 
      // Бэкенд сам пришлет обновление по WebSocket, и карточка сдвинется сама.
    } catch (error) {
      console.error("Ошибка при обновлении статуса:", error);
    }
  };

  // 3. ВЫПОЛНЕНИЕ ТЗ: Подключение к WebSocket для Real-time обновлений
  useEffect(() => {
    // Сначала скачиваем текущие задачи из базы данных
    fetchTasks();

    // Если на доску зашел анонимный пользователь без ID, сокеты не открываем
    if (!userId) return;

    // Открываем постоянное живое соединение с бэкендом
    const wsUrl = `${WS_BASE}/ws/${userId}`;
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        // Ловим событие создания новой задачи ИИ-воркером или ботом
        if (message.event === 'task_created') {
          setTasks((prevTasks) => {
            // Защита от дубликатов в интерфейсе
            if (prevTasks.some(t => t.id === message.data.id)) return prevTasks;
            return [...prevTasks, message.data];
          });
        }
        
        // Ловим событие ручного перетаскивания (смены статуса)
        if (message.event === 'task_updated') {
          setTasks((prevTasks) =>
            prevTasks.map((t) =>
              t.id === message.data.id ? { ...t, status: message.data.status } : t
            )
          );
        }
      } catch (err) {
        console.error("Ошибка обработки сокет-сообщения:", err);
      }
    };

    // Автоматический перезапуск сокета при обрыве интернета
    socket.onclose = () => {
      console.log("Сессия WebSocket закрыта. Повторное подключение через 5 секунд...");
      setTimeout(() => fetchTasks(), 5000); 
    };

    return () => {
      socket.close();
    };
  }, [userId]);

  const renderColumn = (title, statusName, emoji) => {
    const filteredTasks = tasks.filter(t => t.status === statusName);
    return (
      <div className="kanban-column">
        <h2>{emoji} {title} ({filteredTasks.length})</h2>
        <div className="task-list">
          {filteredTasks.map(task => (
            <div key={task.id} className="task-card">
              <h3>{task.title}</h3>
              <p>{task.description}</p>
              <div className="task-actions">
                {statusName !== 'pending' && (
                  <button onClick={() => updateStatus(task.id, 'pending')}>📥 В ожидание</button>
                )}
                {statusName !== 'in_progress' && (
                  <button onClick={() => updateStatus(task.id, 'in_progress')}>⚡ В процесс</button>
                )}
                {statusName !== 'completed' && (
                  <button onClick={() => updateStatus(task.id, 'completed')}>✅ Завершить</button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="app-container">
      <header style={{ marginBottom: '30px', textAlign: 'center' }}>
        <h1 style={{
          color: '#2c3e50',
          margin: '0 0 5px 0',
          fontSize: '1.8rem',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '12px',
          flexWrap: 'wrap',
          lineHeight: '1.2'
        }}>
          <span>Доска задач</span>
          {userId && (
            <span style={{
              backgroundColor: '#3182ce',
              color: '#ffffff',
              fontSize: '0.85rem',
              padding: '4px 12px',
              borderRadius: '20px',
              fontWeight: '600'
            }}>
              ID: {userId}
            </span>
          )}
        </h1>
        <p style={{ color: '#718096', margin: '0', fontSize: '0.95rem' }}>
          {userId ? 'Вы видите свои персональные задачи (Real-time сокеты включены)' : 'Отображение всех задач системы'}
        </p>
      </header>

      <div className="kanban-board">
        {renderColumn('В ожидании', 'pending', '📥')}
        {renderColumn('В процессе', 'in_progress', '⚡')}
        {renderColumn('Завершено', 'completed', '✅')}
      </div>
    </div>
  );
}

export default App;
