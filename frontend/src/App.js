// --- frontend/src/App.js ---
import React, { useEffect, Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { ThemeProvider, CssBaseline, Box, CircularProgress } from '@mui/material';
import { QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { queryClient } from './queryClient.js';
import { theme, globalStyles } from './theme.js';
import { useUserStore, useUserActions } from './store/userStore.js';
import Layout from './components/Layout.js';

import ErrorBoundary from './components/ErrorBoundary.js';
import { useFeatureFlag } from 'hooks/useFeatureFlag.js';

const HomePage = lazy(() => import('./pages/Home/HomePage.js'));
const LoginPage = lazy(() => import('./pages/Login/LoginPage.js'));
const DashboardPage = lazy(() => import('./pages/Dashboard/DashboardPage.js'));
const ScenariosPage = lazy(() => import('./pages/Scenarios/ScenarioPage.js'));
const BillingPage = lazy(() => import('./pages/Billing/BillingPage.js'));
const TeamPage = lazy(() => import('./pages/Team/TeamPage.js'));
const ScenarioEditorPage = lazy(() => import('./pages/Scenarios/editor/ScenarioEditorPage.js'));
const ForbiddenPage = lazy(() => import('./pages/Forbidden/ForbiddenPage.js'));

const FullscreenLoader = () => (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <CircularProgress size={60} />
    </Box>
);

const PrivateRoutes = () => {
    const jwtToken = useUserStore(state => state.jwtToken);
    const isLoading = useUserStore(state => state.isLoading);

    if (isLoading) {
        return <FullscreenLoader />;
    }
    
    return jwtToken ? <Outlet /> : <Navigate to="/login" replace />;
};

const ProtectedRoute = ({ feature, children }) => {
    const { isFeatureAvailable } = useFeatureFlag();
    if (!feature || isFeatureAvailable(feature)) {
        return children;
    }
    return <Navigate to="/forbidden" replace />;
};

function App() {
  const jwtToken = useUserStore(state => state.jwtToken);
  const isLoading = useUserStore(state => state.isLoading);
  const { loadUser, finishInitialLoad } = useUserActions();

  useEffect(() => {
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
                  <Route path="/forbidden" element={<ForbiddenPage />} />

                  <Route element={<PrivateRoutes />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route path="/scenarios" element={
                        <ProtectedRoute feature="scenarios">
                            <ScenariosPage />
                        </ProtectedRoute>
                    } />
                    <Route path="/scenarios/new" element={
                        <ProtectedRoute feature="scenarios">
                            <ScenarioEditorPage />
                        </ProtectedRoute>
                    } />
                    <Route path="/scenarios/:id" element={
                        <ProtectedRoute feature="scenarios">
                            <ScenarioEditorPage />
                        </ProtectedRoute>
                    } />
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