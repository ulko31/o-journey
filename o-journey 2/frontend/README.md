# O! Journey — React map prototype

Новый фронтенд вынесен в `frontend/` и **не заменяет** старый HTML. Для запуска в PyCharm:

```bash
cd frontend
npm install
npm run dev
```

Открыть адрес, указанный Vite (обычно http://localhost:5173). Нужен интернет для тайлов OpenStreetMap. `npm run build` проверяет production-сборку.

В интерактивной карте: три маршрута (включая маршрут по трём странам), метки и переключение точек, построение **схематической линии** по прямым, список желаний без системного prompt. Данные мест — иллюстративные; реальные расписания, отели, льготы, погода и цены **не подключены**. Это не навигационный роутинг.

На Vercel нужен **отдельный проект** из того же GitHub-репозитория с Root Directory `o-journey 2/frontend`, Framework Preset `Vite`, Build Command `npm run build`, Output Directory `dist`. Текущий проект `o-journey-backend` менять на фронтенд нельзя.
