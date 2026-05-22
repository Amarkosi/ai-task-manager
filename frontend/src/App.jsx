import { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [tasks, setTasks] = useState([]);


  const urlParams = new URLSearchParams(window.location.search);
  const userId = urlParams.get('user_id');


const API_URL = 'http://localhost:8000/tasks';


  const fetchTasks = async () => {
    try {
      // Если ID есть — фильтруем, если нет — запрашиваем все задачи
      const config = userId ? { params: { user_id: userId } } : {};
      const response = await axios.get(API_URL, config);
      setTasks(response.data);
    } catch (error) {
      console.error("Ошибка при получении задач:", error);
    }
  };


  const updateStatus = async (taskId, newStatus) => {
    try {
      await axios.patch(`http://localhost:8000/tasks/${taskId}`, { status: newStatus });
      fetchTasks();
    } catch (error) {
      console.error("Ошибка при обновлении статуса:", error);
    }
  };

  useEffect(() => {
    fetchTasks();
    const interval = setInterval(fetchTasks, 3000);
    return () => clearInterval(interval);
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
      {/*Заголовок*/}
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
          {userId ? 'Вы видите свои персональные задачи' : 'Отображение всех задач системы'}
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