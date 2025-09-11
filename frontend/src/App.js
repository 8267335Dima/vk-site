// frontend/src/App.js
import React, { useEffect, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';

// Локальные импорты
import { theme, globalStyles } from './theme.js';
import { WebSocketProvider } from './contexts/WebSocketProvider.js';
import { useUserStore } from './store/userStore.js';
import Layout from './components/Layout.js';
import ErrorBoundary from './components/ErrorBoundary.js';

// Ленивая загрузка страниц для улучшения производительности
const HomePage = lazy(() => import('./pages/Home/HomePage.js'));
const LoginPage = lazy(() => import('./pages/Login/LoginPage.js'));
const DashboardPage = lazy(() => import('./pages/Dashboard/DashboardPage.js'));
const ScenariosPage = lazy(() => import('./pages/Scenarios/ScenarioPage.js'));
const BillingPage = lazy(() => import('./pages/Billing/BillingPage.js'));

// Конфигурация React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 минут
      retry: 1, // Повторять запрос при ошибке 1 раз
    },
  },
});

// Компонент-загрузчик на весь экран
const FullscreenLoader = () => (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
    </Box>
);

/**
 * Компонент-"охранник" для приватных роутов.
 * Он не рендерит UI, а только проверяет авторизацию.
 * Если пользователь авторизован, он рендерит дочерние роуты (`<Outlet />`),
 * обернув их в WebSocketProvider. В противном случае — перенаправляет на страницу входа.
 */
const PrivateRoutes = () => {
    const { jwtToken, isLoading } = useUserStore(state => ({ jwtToken: state.jwtToken, isLoading: state.isLoading }));

    if (isLoading) {
        return <FullscreenLoader />;
    }
    
    return jwtToken ? (
        <WebSocketProvider>
            <Outlet /> 
        </WebSocketProvider>
    ) : <Navigate to="/login" replace />;
};


function App() {
  const { jwtToken, isLoading, loadUser, finishInitialLoad } = useUserStore(state => ({
      jwtToken: state.jwtToken,
      isLoading: state.isLoading,
      loadUser: state.loadUser,
      finishInitialLoad: state.finishInitialLoad
  }));

  // Этот эффект отвечает за начальную загрузку данных пользователя
  // или завершение загрузки, если токена нет.
  useEffect(() => {
    if (jwtToken) {
      loadUser();
    } else {
      finishInitialLoad();
    }
  }, [jwtToken, loadUser, finishInitialLoad]);

  // Показываем глобальный загрузчик, пока идет самая первая проверка токена
  if (isLoading) {
    return <FullscreenLoader />;
  }
  
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Toaster
          position="bottom-right"
          toastOptions={{
            className: 'toaster-custom',
            style: {
              background: 'rgba(30, 31, 37, 0.9)',
              backdropFilter: 'blur(10px)',
              color: '#FFFFFF',
              borderRadius: '12px',
              border: '1px solid rgba(160, 163, 189, 0.15)',
              boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.2)',
            },
          }}
          containerStyle={{
            maxHeight: 'calc(3 * (60px + 16px))',
            overflow: 'hidden',
          }}
        />
        <style>{globalStyles}</style>
        <Router>
          <ErrorBoundary>
            <Suspense fallback={<FullscreenLoader />}>
              <Routes>
                {/* 
                  Layout теперь является единой точкой входа для всех страниц.
                  Он рендерит шапку и футер, а внутри себя через <Outlet /> 
                  отображает нужную страницу в зависимости от URL.
                */}
                <Route element={<Layout />}>
                  
                  {/* --- Публичные роуты --- */}
                  <Route path="/" element={<HomePage />} />
                  <Route path="/login" element={jwtToken ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
                  <Route path="/billing" element={<BillingPage />} />

                  {/* --- Приватные роуты, защищенные "охранником" PrivateRoutes --- */}
                  <Route element={<PrivateRoutes />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/scenarios" element={<ScenariosPage />} />
                  </Route>

                  {/* --- Обработка всех остальных путей (404) --- */}
                  <Route path="*" element={<Navigate to="/" replace />} />

                </Route>
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </Router>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;