// frontend/src/App.js
import React, { useEffect, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { theme, globalStyles } from './theme.js';
import { WebSocketProvider } from './contexts/WebSocketProvider.js';
import { useUserStore } from './store/userStore.js';

import Layout from './components/Layout.v2.js';
import HomePage from './pages/Home/HomePage.js';
import LoginPage from './pages/Login/LoginPage.js';
import ErrorBoundary from './components/ErrorBoundary.js';

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

const PrivateRoute = ({ children }) => {
    const { jwtToken, isLoading } = useUserStore(state => ({ jwtToken: state.jwtToken, isLoading: state.isLoading }));
    if (isLoading) return <FullscreenLoader />;
    return jwtToken ? children : <Navigate to="/login" replace />;
};

function App() {
  const { jwtToken, loadUser, finishInitialLoad } = useUserStore(state => ({
      jwtToken: state.jwtToken,
      loadUser: state.loadUser,
      finishInitialLoad: state.finishInitialLoad
  }));

  useEffect(() => {
    jwtToken ? loadUser() : finishInitialLoad();
  }, [jwtToken, loadUser, finishInitialLoad]);

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
            // --- ОГРАНИЧЕНИЕ КОЛИЧЕСТВА УВЕДОМЛЕНИЙ ---
            // Этот трюк с CSS ограничивает видимое количество уведомлений
            maxHeight: 'calc(3 * (60px + 16px))', // 3 * (высота тоста + отступ)
            overflow: 'hidden',
          }}
        />
        <style>{globalStyles}</style>
        <Router>
          <ErrorBoundary>
            <Suspense fallback={<FullscreenLoader />}>
              <Routes>
                  <Route path="/" element={<Layout><HomePage /></Layout>} />
                  <Route path="/login" element={jwtToken ? <Navigate to="/dashboard" replace /> : <Layout><LoginPage /></Layout>} />
                  <Route path="/billing" element={<Layout><BillingPage /></Layout>} />
                  
                  <Route element={
                      <PrivateRoute>
                          <WebSocketProvider>
                            <Layout /> 
                          </WebSocketProvider>
                      </PrivateRoute>
                  }>
                      <Route path="/dashboard" element={<DashboardPage />} />
                      <Route path="/scenarios" element={<ScenariosPage />} />
                      {/* История теперь является частью Дашборда, отдельная страница не нужна */}
                  </Route>
                  
                  <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
          </ErrorBoundary>
        </Router>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;