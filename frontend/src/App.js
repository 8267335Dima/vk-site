// frontend/src/App.js - ОБНОВЛЕННАЯ ВЕРСИЯ

import React, { useEffect, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';

import { theme, globalStyles } from './theme.js';
// --- ИЗМЕНЕНИЕ: WebSocketProvider больше не нужен ---
// import { WebSocketProvider } from './contexts/WebSocketProvider.js'; 
import { useUserStore, useUserActions } from './store/userStore.js';
import Layout from './components/Layout.js';
import ErrorBoundary from './components/ErrorBoundary.js';

// Lazy-loaded компоненты остаются без изменений
const HomePage = lazy(() => import('./pages/Home/HomePage.js'));
const LoginPage = lazy(() => import('./pages/Login/LoginPage.js'));
const DashboardPage = lazy(() => import('./pages/Dashboard/DashboardPage.js'));
const ScenariosPage = lazy(() => import('./pages/Scenarios/ScenarioPage.js'));
const BillingPage = lazy(() => import('./pages/Billing/BillingPage.js'));

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 1000 * 60 * 5, retry: 1 } },
});

const FullscreenLoader = () => (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
    </Box>
);

const PrivateRoutes = () => {
    const jwtToken = useUserStore(state => state.jwtToken);
    const isLoading = useUserStore(state => state.isLoading);

    if (isLoading) {
        return <FullscreenLoader />;
    }
    
    // --- ИЗМЕНЕНИЕ: Убрали обертку WebSocketProvider. Теперь соединение управляется глобально. ---
    return jwtToken ? <Outlet /> : <Navigate to="/login" replace />;
};

function App() {
  const jwtToken = useUserStore(state => state.jwtToken);
  const isLoading = useUserStore(state => state.isLoading);
  const { loadUser, finishInitialLoad } = useUserActions();

  useEffect(() => {
    // Эта логика остается, она важна для загрузки данных пользователя
    if (jwtToken) {
      loadUser();
    } else {
      finishInitialLoad();
    }
  }, [jwtToken, loadUser, finishInitialLoad]);

  if (isLoading) {
    return <FullscreenLoader />;
  }
  
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Toaster position="bottom-right" toastOptions={{ style: { background: '#17181D', color: '#FFFFFF', border: '1px solid rgba(160, 163, 189, 0.15)' } }} />
        <style>{globalStyles}</style>
        <Router>
          <ErrorBoundary>
            <Suspense fallback={<FullscreenLoader />}>
              <Routes>
                <Route element={<Layout />}>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/login" element={jwtToken ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
                  <Route path="/billing" element={<BillingPage />} />
                  <Route element={<PrivateRoutes />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/scenarios" element={<ScenariosPage />} />
                  </Route>
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