// frontend/src/App.js
import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import { QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';

import { queryClient } from './queryClient.js';
import { theme } from './theme.js';
import { useStore } from './store';
import Layout from './components/Layout.js';
import ErrorBoundary from './components/ErrorBoundary.js';
import { useCurrentUser } from './hooks/useCurrentUser.js';
import { useFeatureFlag } from './hooks/useFeatureFlag.js';

// Lazy-loaded pages
const HomePage = lazy(() => import('./pages/Home/HomePage.js'));
const LoginPage = lazy(() => import('./pages/Login/LoginPage.js'));
const DashboardPage = lazy(() => import('./pages/Dashboard/DashboardPage.js'));
const ScenariosPage = lazy(() => import('./pages/Scenarios/ScenarioPage.js'));
const BillingPage = lazy(() => import('./pages/Billing/BillingPage.js'));
const TeamPage = lazy(() => import('./pages/Team/TeamPage.js'));
const ScenarioEditorPage = lazy(() => import('./pages/Scenarios/editor/ScenarioEditorPage.js'));
const ForbiddenPage = lazy(() => import('./pages/Forbidden/ForbiddenPage.js'));
const PostsPage = lazy(() => import('./pages/Posts/PostsPage.js'));

const FullscreenLoader = () => (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress size={60} />
    </Box>
);

// Rationale: Этот компонент проверяет, аутентифицирован ли пользователь.
// Он использует useCurrentUser, который проверяет валидность токена через реальный API-запрос.
// Это надежнее, чем просто проверять наличие токена в localStorage.
const PrivateRoutes = () => {
    const { isSuccess, isLoading } = useCurrentUser();
    const isAuthenticated = useStore(state => state.isAuthenticated);

    if (isLoading) {
        return <FullscreenLoader />;
    }

    // Успешный запрос к API и наличие флага в сторе - единственное условие для доступа.
    if (isSuccess && isAuthenticated) {
        return <Outlet />;
    }

    return <Navigate to="/login" replace />;
};

// Rationale: Этот компонент-обертка проверяет, доступна ли фича пользователю по его тарифу.
// Он получает данные из useFeatureFlag, который, в свою очередь, берет их из useCurrentUser.
const ProtectedRoute = ({ feature, children }) => {
    const { isFeatureAvailable } = useFeatureFlag();
    if (!feature || isFeatureAvailable(feature)) {
        return children;
    }
    return <Navigate to="/forbidden" replace />;
};

function App() {
  const isAuthenticated = useStore(state => state.isAuthenticated);
  
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Toaster position="bottom-right" toastOptions={{ style: { background: '#17181D', color: '#FFFFFF', border: '1px solid rgba(160, 163, 189, 0.15)' } }} />
        <Router>
          <ErrorBoundary>
            <Suspense fallback={<FullscreenLoader />}>
              <Routes>
                <Route element={<Layout />}>
                  <Route path="/" element={<HomePage />} />
                  <Route path="/login" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
                  <Route path="/billing" element={<BillingPage />} />
                  <Route path="/forbidden" element={<ForbiddenPage />} />

                  <Route element={<PrivateRoutes />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/scenarios" element={
                        <ProtectedRoute feature="scenarios">
                            <ScenariosPage />
                        </ProtectedRoute>
                    } />
                    <Route path="/scenarios/:id" element={
                        <ProtectedRoute feature="scenarios">
                            <ScenarioEditorPage />
                        </ProtectedRoute>
                    } />
                    <Route path="/posts" element={
                        <ProtectedRoute feature="post_scheduler">
                            <PostsPage />
                        </ProtectedRoute>
                    }/>
                    <Route path="/team" element={
                        <ProtectedRoute feature="agency_mode">
                            <TeamPage />
                        </ProtectedRoute>
                    } />
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