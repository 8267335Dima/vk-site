import React, { Suspense, lazy } from 'react';
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
  Outlet,
} from 'react-router-dom';
import {
  ThemeProvider,
  CssBaseline,
  Box,
  CircularProgress,
} from '@mui/material';
import { QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';

import { queryClient } from '@/shared/api/queryClient';
import { theme } from '@/shared/config/theme';
import { useStore } from '@/app/store';
import Layout from '@/shared/ui/Layout/Layout';
import ErrorBoundary from '@/shared/ui/ErrorBoundary/ErrorBoundary';
import { useCurrentUser } from '@/shared/lib/hooks/useCurrentUser';
import { useFeatureFlag } from '@/shared/lib/hooks/useFeatureFlag';

// Lazy-loaded pages
const HomePage = lazy(() => import('@/pages/home/HomePage'));
const LoginPage = lazy(() => import('@/pages/login/LoginPage'));
const DashboardPage = lazy(() => import('@/pages/dashboard/DashboardPage'));
const ScenariosPage = lazy(() => import('@/pages/scenarios/ScenarioPage'));
const BillingPage = lazy(() => import('@/pages/billing/BillingPage'));
const TeamPage = lazy(() => import('@/pages/team/TeamPage'));
const ScenarioEditorPage = lazy(
  () => import('@/pages/scenarios/editor/ScenarioEditorPage')
);
const ForbiddenPage = lazy(() => import('@/pages/forbidden/ForbiddenPage'));
const PostsPage = lazy(() => import('@/pages/posts/PostsPage'));

const FullscreenLoader = () => (
  <Box
    sx={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
    }}
  >
    <CircularProgress size={60} />
  </Box>
);

const PrivateRoutes = () => {
  const { isSuccess, isLoading } = useCurrentUser();
  const isAuthenticated = useStore((state) => state.isAuthenticated);

  if (isLoading) {
    return <FullscreenLoader />;
  }

  if (isSuccess && isAuthenticated) {
    return <Outlet />;
  }

  return <Navigate to="/login" replace />;
};

const ProtectedRoute = ({ feature, children }) => {
  const { isFeatureAvailable } = useFeatureFlag();
  if (!feature || isFeatureAvailable(feature)) {
    return children;
  }
  return <Navigate to="/forbidden" replace />;
};

function App() {
  const isAuthenticated = useStore((state) => state.isAuthenticated);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#17181D',
              color: '#FFFFFF',
              border: '1px solid rgba(160, 163, 189, 0.15)',
            },
          }}
        />
        <Router>
          <ErrorBoundary>
            <Suspense fallback={<FullscreenLoader />}>
              <Routes>
                <Route element={<Layout />}>
                  <Route path="/" element={<HomePage />} />
                  <Route
                    path="/login"
                    element={
                      isAuthenticated ? (
                        <Navigate to="/dashboard" replace />
                      ) : (
                        <LoginPage />
                      )
                    }
                  />
                  <Route path="/billing" element={<BillingPage />} />
                  <Route path="/forbidden" element={<ForbiddenPage />} />

                  <Route element={<PrivateRoutes />}>
                    <Route path="/dashboard" element={<DashboardPage />} />
                    <Route
                      path="/scenarios"
                      element={
                        <ProtectedRoute feature="scenarios">
                          <ScenariosPage />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/scenarios/:id"
                      element={
                        <ProtectedRoute feature="scenarios">
                          <ScenarioEditorPage />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/posts"
                      element={
                        <ProtectedRoute feature="post_scheduler">
                          <PostsPage />
                        </ProtectedRoute>
                      }
                    />
                    <Route
                      path="/team"
                      element={
                        <ProtectedRoute feature="agency_mode">
                          <TeamPage />
                        </ProtectedRoute>
                      }
                    />
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
