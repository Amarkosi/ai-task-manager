import { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [tasks, setTasks] = useState([]);

  // Вытаскиваем user_id из URL параметров (?user_id=12345)
  const urlParams = new URLSearchParams(window.location.search);
  const userId = urlParams.get('user_id');

  // Читаем адрес бэкенда из переменных окружения Vite
  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
  
  // Универсальное правило http->ws и https->wss для защиты от сброса сессии WebSocket
  const WS_BASE = API_BASE.startsWith('https') 
    ? API_BASE.replace(/^https/, 'wss') 
    : API_BASE.replace(/^http/, 'ws');

  // 1. Функция загрузки задач из базы через HTTP (загружает и старые задачи сразу)
  const fetchTasks = async () => {
    try {
      const config = userId ? { params: { user_id: userId } } : {};
      const response = await axios.get(`${API_BASE}/tasks`, config);
      setTasks(response.data);
    } catch (error) {
      console.error("Ошибка при получении задач:", error);
    }
  };

  // 2. Функция обновления статуса задачи
  const updateStatus = async (taskId, newStatus) => {
    try {
      await axios.patch(`${API_BASE}/tasks/${taskId}`, { status: newStatus });
    } catch (error) {
      console.error("Ошибка при обновлении статуса:", error);
    }
  };

  // 3. Функция удаления задачи из базы данных
  const deleteTask = async (taskId) => {
    try {
      await axios.delete(`${API_BASE}/tasks/${taskId}`);
      // Локально убираем из списка, чтобы интерфейс обновился мгновенно
      setTasks((prevTasks) => prevTasks.filter((t) => t.id !== taskId));
    } catch (error) {
      console.error("Ошибка при удалении задачи:", error);
    }
  };

  // 4. Подключение к WebSocket для Real-time обновлений
  useEffect(() => {
    // Скачиваем текущие/старые задачи сразу при открытии доски
    fetchTasks();

    if (!userId) return;

    const wsUrl = `${WS_BASE}/ws/${userId}`;
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        if (message.event === 'task_created') {
          setTasks((prevTasks) => {
            if (prevTasks.some(t => t.id === message.data.id)) return prevTasks;
            return [...prevTasks, message.data];
          });
        }
        
        if (message.event === 'task_updated') {
          setTasks((prevTasks) =>
            prevTasks.map((t) =>
              t.id === message.data.id ? { ...t, status: message.data.status } : t
            )
          );
        }

        if (message.event === 'task_deleted') {
          setTasks((prevTasks) => prevTasks.filter((t) => t.id !== message.data.id));
        }
      } catch (err) {
        console.error("Ошибка обработки сокет-сообщения:", err);
      }
    };

    socket.onclose = () => {
      setTimeout(() => fetchTasks(), 5000); 
    };

    return () => {
      socket.close();
    };
  }, [userId]);

  // Функция для отрисовки отдельной колонки Канбан-доски
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
              
              {/* ИСПРАВЛЕНО: Кнопки теперь выстроены в строгий вертикальный столбик друг под другом */}
              <div className="task-actions" style={{ 
                display: 'flex', 
                flexDirection: 'column', 
                gap: '8px', 
                marginTop: '15px',
                width: '100%'
              }}>
                {statusName !== 'pending' && (
                  <button style={{ color: '#000000', fontWeight: '500', width: '100%', padding: '8px' }} onClick={() => updateStatus(task.id, 'pending')}>📥 В ожидание</button>
                )}
                {statusName !== 'in_progress' && (
                  <button style={{ color: '#000000', fontWeight: '500', width: '100%', padding: '8px' }} onClick={() => updateStatus(task.id, 'in_progress')}>⚡ В процесс</button>
                )}
                {statusName !== 'completed' && (
                  <button style={{ color: '#000000', fontWeight: '500', width: '100%', padding: '8px' }} onClick={() => updateStatus(task.id, 'completed')}>✅ Завершить</button>
                )}
                <button 
                  style={{ 
                    color: '#ffffff', 
                    backgroundColor: '#e53e3e', 
                    fontWeight: '500', 
                    width: '100%',
                    padding: '8px',
                    marginTop: '4px'
                  }} 
                  onClick={() => deleteTask(task.id)}
                >
                  🗑️ Удалить
                </button>
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
