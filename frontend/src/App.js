// frontend/src/App.js
import React, { useEffect, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { theme, globalStyles } from './theme.js';
import { WebSocketProvider } from './contexts/WebSocketProvider';
import { useUserStore } from './store/userStore';

import Layout from './components/Layout';
import HomePage from './pages/Home/HomePage';
import LoginPage from './pages/Login/LoginPage';
import ErrorBoundary from './components/ErrorBoundary';

// Lazy loading for all major pages
const DashboardPage = lazy(() => import('./pages/Dashboard/DashboardPage'));
const HistoryPage = lazy(() => import('./pages/History/HistoryPage'));
const ScenariosPage = lazy(() => import('./pages/Scenarios/ScenarioPage'));
const BillingPage = lazy(() => import('./pages/Billing/BillingPage'));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
});

const FullscreenLoader = () => (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress />
    </Box>
);

const PrivateRoute = ({ children }) => {
    const jwtToken = useUserStore(state => state.jwtToken);
    const isLoading = useUserStore(state => state.isLoading);

    if (isLoading) {
        return <FullscreenLoader />;
    }

    return jwtToken ? children : <Navigate to="/login" replace />;
};

function App() {
  const jwtToken = useUserStore(state => state.jwtToken);
  const loadUser = useUserStore(state => state.loadUser);
  const finishInitialLoad = useUserStore(state => state.finishInitialLoad);

  useEffect(() => {
    if (jwtToken) {
      loadUser();
    } else {
      finishInitialLoad();
    }
  }, [jwtToken, loadUser, finishInitialLoad]);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: 'rgba(40, 40, 50, 0.8)',
              backdropFilter: 'blur(10px)',
              color: '#F5F5F5',
              borderRadius: '12px',
              boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.3)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            },
          }}
        />
        {/* --- ИЗМЕНЕНИЕ: Глобальные стили теперь применяются здесь --- */}
        <style>{globalStyles}</style>
        <Router>
          {/* --- ИЗМЕНЕНИЕ: Layout теперь не оборачивает всё приложение, а используется внутри роутов --- */}
          <ErrorBoundary>
            <Suspense fallback={<FullscreenLoader />}>
              <Routes>
                  <Route path="/" element={<Layout><HomePage /></Layout>} />
                  <Route path="/login" element={jwtToken ? <Navigate to="/dashboard" replace /> : <Layout><LoginPage /></Layout>} />
                  <Route path="/billing" element={<Layout><BillingPage /></Layout>} />
                  
                  {/* --- ИЗМЕНЕНИЕ: Приватные роуты с общим Layout --- */}
                  <Route element={
                      <PrivateRoute>
                          <WebSocketProvider>
                            <Layout /> 
                          </WebSocketProvider>
                      </PrivateRoute>
                  }>
                      <Route path="/dashboard" element={<DashboardPage />} />
                      <Route path="/scenarios" element={<ScenariosPage />} />
                      <Route path="/history" element={<HistoryPage />} />
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