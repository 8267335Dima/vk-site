

// --- frontend/src\api.js ---

// frontend/src/api.js
import axios from 'axios';
import { useUserStore } from 'store/userStore';

export const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || '',
});

apiClient.interceptors.request.use((config) => {
  const token = useUserStore.getState().jwtToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      useUserStore.getState().actions.logout(); 
    }
    return Promise.reject(error);
  }
);

// --- Auth ---
export const loginWithVkToken = (vkToken) => apiClient.post('/api/v1/auth/vk', { vk_token: vkToken });

// --- User ---
export const fetchUserInfo = () => apiClient.get('/api/v1/users/me');
export const fetchUserLimits = () => apiClient.get('/api/v1/users/me/limits');
export const updateUserDelayProfile = (profile) => apiClient.put('/api/v1/users/me/delay-profile', profile);
export const fetchTaskInfo = (taskKey) => apiClient.get(`/api/v1/users/task-info?task_key=${taskKey}`);

// --- Tasks & History ---
export const runTask = (taskKey, params) => apiClient.post(`/api/v1/tasks/run/${taskKey}`, params);
export const fetchTaskHistory = ({ pageParam = 1 }, filters) => {
    const params = new URLSearchParams({ page: pageParam, size: 25 });
    if (filters.status) {
        params.append('status', filters.status);
    }
    return apiClient.get(`/api/v1/tasks/history?${params.toString()}`).then(res => res.data);
};
export const cancelTask = (taskHistoryId) => apiClient.post(`/api/v1/tasks/${taskHistoryId}/cancel`);
export const retryTask = (taskHistoryId) => apiClient.post(`/api/v1/tasks/${taskHistoryId}/retry`);

// --- Stats & Analytics ---
export const fetchActivityStats = (days = 7) => apiClient.get(`/api/v1/stats/activity?days=${days}`).then(res => res.data);
export const fetchAudienceAnalytics = () => apiClient.get('/api/v1/analytics/audience').then(res => res.data);
export const fetchProfileGrowth = (days = 30) => apiClient.get(`/api/v1/analytics/profile-growth?days=${days}`).then(res => res.data);
export const fetchProfileSummary = () => apiClient.get('/api/v1/analytics/profile-summary').then(res => res.data);

// --- Automations ---
export const fetchAutomations = () => apiClient.get('/api/v1/automations').then(res => res.data);
export const updateAutomation = ({ automationType, isActive, settings }) => apiClient.post(`/api/v1/automations/${automationType}`, { is_active: isActive, settings: settings || {} }).then(res => res.data);

// --- Billing ---
export const fetchAvailablePlans = () => apiClient.get('/api/v1/billing/plans').then(res => res.data);
export const createPayment = (planId, months) => apiClient.post('/api/v1/billing/create-payment', { plan_id: planId, months }).then(res => res.data);

// --- Scenarios ---
export const fetchScenarios = () => apiClient.get('/api/v1/scenarios').then(res => res.data);
export const createScenario = (data) => apiClient.post('/api/v1/scenarios', data).then(res => res.data);
export const updateScenario = ({ id, ...data }) => apiClient.put(`/api/v1/scenarios/${id}`, data).then(res => res.data);
export const deleteScenario = (id) => apiClient.delete(`/api/v1/scenarios/${id}`);

// --- Notifications ---
export const fetchNotifications = () => apiClient.get('/api/v1/notifications').then(res => res.data);
export const markNotificationsAsRead = () => apiClient.post('/api/v1/notifications/read');

// --- Proxies ---
export const fetchProxies = () => apiClient.get('/api/v1/proxies').then(res => res.data);
export const addProxy = (proxyUrl) => apiClient.post('/api/v1/proxies', { proxy_url: proxyUrl }).then(res => res.data);
export const deleteProxy = (id) => apiClient.delete(`/api/v1/proxies/${id}`);

// --- frontend/src\App.js ---

// frontend/src/App.js
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

const HomePage = lazy(() => import('./pages/Home/HomePage.js'));
const LoginPage = lazy(() => import('./pages/Login/LoginPage.js'));
const DashboardPage = lazy(() => import('./pages/Dashboard/DashboardPage.js'));
const ScenariosPage = lazy(() => import('./pages/Scenarios/ScenarioPage.js'));
const BillingPage = lazy(() => import('./pages/Billing/BillingPage.js'));

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
    // <-- ИЗМЕНЕНИЕ 3: Используем импортированный queryClient
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

// --- frontend/src\index.js ---

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// --- frontend/src\queryClient.js ---

// frontend/src/queryClient.js
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 минут
      retry: 1,
    },
  },
});

// --- frontend/src\theme.js ---

// frontend/src/theme.js
import { createTheme, responsiveFontSizes } from '@mui/material/styles';

// --- ИЗМЕНЕНИЕ: Обновленная, более глубокая и стильная палитра ---
const palette = {
  primary: '#5E5CE6',
  secondary: '#00BAE2',
  backgroundDefault: '#0A0A0B', // Более глубокий черный
  backgroundPaper: '#161618',  // Более контрастный серый
  textPrimary: '#F5F5F7',      // Слегка смягченный белый
  textSecondary: '#A0A3BD',
  success: '#32D74B',          // Более яркий зеленый
  warning: '#FF9F0A',          // Более яркий оранжевый
  error: '#FF453A',            // Более яркий красный
  info: '#0A84FF',
  divider: 'rgba(160, 163, 189, 0.15)',
};

let theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: palette.primary },
    secondary: { main: palette.secondary },
    background: {
      default: palette.backgroundDefault,
      paper: palette.backgroundPaper,
    },
    text: {
      primary: palette.textPrimary,
      secondary: palette.textSecondary,
    },
    success: { main: palette.success },
    warning: { main: palette.warning },
    error: { main: palette.error },
    info: { main: palette.info },
    divider: palette.divider,
  },
  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    h1: { fontWeight: 800, letterSpacing: '-0.03em' },
    h2: { fontWeight: 700, letterSpacing: '-0.025em' },
    h3: { fontWeight: 700, letterSpacing: '-0.02em' },
    h4: { fontWeight: 600, letterSpacing: '-0.01em' },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    button: {
        textTransform: 'none',
        fontWeight: 600,
        fontSize: '1rem',
    }
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: `1px solid ${palette.divider}`,
          borderRadius: '16px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '12px',
          padding: '10px 24px',
          transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: `0 8px 20px ${palette.primary}40`,
          },
        },
        contained: {
          boxShadow: 'none',
          '&:hover': {
             boxShadow: `0 8px 20px ${palette.primary}40`,
          }
        },
        containedPrimary: {
           background: `linear-gradient(45deg, ${palette.primary} 30%, ${palette.secondary} 90%)`,
        }
      },
    },
    MuiTooltip: {
        styleOverrides: {
            tooltip: {
                backgroundColor: 'rgba(30, 31, 37, 0.9)',
                backdropFilter: 'blur(8px)',
                borderRadius: '8px',
                border: `1px solid ${palette.divider}`,
                fontSize: '0.875rem',
                padding: '12px',
            },
            arrow: {
                color: 'rgba(30, 31, 37, 0.9)',
            }
        }
    },
    MuiChip: {
        styleOverrides: {
            root: {
                borderRadius: '8px',
                fontWeight: 600,
            }
        }
    }
  },
});

theme = responsiveFontSizes(theme);

export { theme };

export const globalStyles = `
  body {
    background-color: ${palette.backgroundDefault};
    color: ${palette.textPrimary};
  }
  
  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb {
    background-color: ${palette.divider};
    border-radius: 4px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background-color: rgba(160, 163, 189, 0.3);
  }
`;

// --- frontend/src\websocket.js ---

// frontend/src/websocket.js
import { toast } from 'react-hot-toast';
import { useUserStore } from 'store/userStore';
import { queryClient } from './queryClient';

let socket = null;
let reconnectInterval = 5000;
let reconnectTimeout = null;

const getSocketUrl = () => {
    const apiUrl = process.env.REACT_APP_API_BASE_URL || window.location.origin;
    const wsUrl = new URL(apiUrl);
    wsUrl.protocol = wsUrl.protocol.replace('http', 'ws');
    wsUrl.pathname = '/api/v1/ws';
    return wsUrl.toString();
};

const handleMessage = (event) => {
    try {
        const { type, payload } = JSON.parse(event.data);
        const { setDailyLimits } = useUserStore.getState().actions;

        switch (type) {
            case 'log':
                console.log('WS Log:', payload);
                break;
            case 'stats_update':
                setDailyLimits({
                    likes_today: payload.likes_count,
                    friends_add_today: payload.friends_added_count
                });
                break;
            case 'task_history_update':
                queryClient.setQueryData(['task_history'], (oldData) => {
                    if (!oldData) return oldData;
                    
                    const newPages = oldData.pages.map(page => ({
                        ...page,
                        items: page.items.map(task => 
                            task.id === payload.task_history_id 
                                ? { ...task, status: payload.status, result: payload.result } 
                                : task
                        )
                    }));

                    return { ...oldData, pages: newPages };
                });

                if (payload.status === 'SUCCESS') {
                    toast.success(`Задача "${payload.task_name}" успешно завершена!`);
                }
                if (payload.status === 'FAILURE') {
                    toast.error(`Задача "${payload.task_name}" провалена: ${payload.result}`, { duration: 8000 });
                }
                break;
            case 'new_notification':
                queryClient.invalidateQueries({ queryKey: ['notifications'] });
                const message = payload.message;
                const options = { duration: 8000 };
                if (payload.level === 'error') toast.error(message, options);
                else if (payload.level === 'warning') toast.error(message, options);
                else toast.success(message, { duration: 5000 });
                break;
            default:
                break;
        }
    } catch (error) {
        console.error("Error parsing WebSocket message:", error);
    }
};

export const connectWebSocket = (token) => {
    if (socket || !token) return;

    const url = `${getSocketUrl()}?token=${token}`;
    socket = new WebSocket(url);

    socket.onopen = () => {
        console.log('WebSocket connected');
        useUserStore.getState().actions.setConnectionStatus('На связи');
        if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };

    socket.onclose = (event) => {
        console.log(`WebSocket disconnected: ${event.code}`);
        socket = null;
        useUserStore.getState().actions.setConnectionStatus('Переподключение...');
        
        const currentToken = useUserStore.getState().jwtToken;
        if (currentToken) {
           reconnectTimeout = setTimeout(() => connectWebSocket(currentToken), reconnectInterval);
        }
    };

    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        // <-- ИЗМЕНЕНИЕ: Добавлена проверка, чтобы избежать ошибки
        if (socket) {
            socket.close();
        }
    };

    socket.onmessage = handleMessage;
};

export const disconnectWebSocket = () => {
    if (reconnectTimeout) clearTimeout(reconnectTimeout);
    if (socket) {
        socket.close();
        socket = null;
        useUserStore.getState().actions.setConnectionStatus('Отключено');
    }
};

// --- frontend/src\components\CountSlider.js ---

// frontend/src/components/CountSlider.js
import React from 'react';
import { Box, Slider, Typography, Tooltip, Input, Grid } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

const CountSlider = ({ label, value, onChange, max, min = 1, step = 1, tooltip }) => {
    
    const handleSliderChange = (event, newValue) => {
        onChange(newValue);
    };

    const handleInputChange = (event) => {
        onChange(event.target.value === '' ? '' : Number(event.target.value));
    };

    const handleBlur = () => {
        if (value < min) {
            onChange(min);
        } else if (value > max) {
            onChange(max);
        }
    };
    
    const progress = (value / max) * 100;
    const trackColor = progress > 85 ? 'error.main' : progress > 60 ? 'warning.main' : 'primary.main';

    return (
        <Box>
            <Box display="flex" alignItems="center" mb={1}>
                <Typography gutterBottom sx={{ fontWeight: 500, mb: 0 }}>
                    {label}
                </Typography>
                {tooltip && (
                    <Tooltip title={tooltip} placement="top" arrow>
                        <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
                    </Tooltip>
                )}
            </Box>
            <Grid container spacing={2} alignItems="center">
                <Grid item xs>
                    <Slider
                        value={typeof value === 'number' ? value : min}
                        onChange={handleSliderChange}
                        aria-labelledby="input-slider"
                        min={min}
                        max={max}
                        step={step}
                        sx={{
                            color: trackColor,
                            transition: 'color 0.3s ease',
                            '& .MuiSlider-rail': {
                                opacity: 0.3,
                            }
                        }}
                    />
                </Grid>
                <Grid item>
                    <Input
                        value={value}
                        size="small"
                        onChange={handleInputChange}
                        onBlur={handleBlur}
                        inputProps={{
                            step: step,
                            min: min,
                            max: max,
                            type: 'number',
                            'aria-labelledby': 'input-slider',
                        }}
                        sx={{ width: '60px' }}
                    />
                </Grid>
            </Grid>
        </Box>
    );
};

export default CountSlider;

// --- frontend/src\components\ErrorBoundary.js ---

// frontend/src/components/ErrorBoundary.js
import React from 'react';
import { Paper, Typography, Button, Box } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    // Обновляем состояние, чтобы следующий рендер показал запасной UI.
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Здесь можно отправить информацию об ошибке в сервис мониторинга (Sentry, LogRocket и т.д.)
    console.error("Uncaught error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      // Вы можете отрендерить любой запасной UI
      return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
            <Paper sx={{ p: 4, textAlign: 'center', maxWidth: 500 }}>
                <ErrorOutlineIcon color="error" sx={{ fontSize: 60, mb: 2 }}/>
                <Typography variant="h5" component="h1" gutterBottom>
                    Что-то пошло не так.
                </Typography>
                <Typography color="text.secondary" sx={{ mb: 3 }}>
                    В приложении произошла ошибка. Пожалуйста, попробуйте перезагрузить страницу.
                </Typography>
                <Button 
                    variant="contained" 
                    onClick={() => window.location.reload()}
                >
                    Перезагрузить
                </Button>
            </Paper>
        </Box>
      );
    }

    return this.props.children; 
  }
}

export default ErrorBoundary;

// --- frontend/src\components\Footer.js ---

// frontend/src/components/Footer.js
import React from 'react';
import { Box, Container, Typography, Stack, Link, Grid } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import { content } from 'content/content';

const FooterLink = ({ to, href, children }) => (
    <Link 
        component={to ? RouterLink : 'a'} 
        to={to} 
        href={href}
        variant="body2" 
        sx={{ 
            color: 'text.secondary', 
            textDecoration: 'none', 
            transition: 'color 0.2s ease-in-out',
            '&:hover': { color: 'primary.main', textDecoration: 'underline' }
        }}
    >
        {children}
    </Link>
);

const FooterTitle = ({ children }) => (
    <Typography variant="overline" sx={{ fontWeight: 600, color: 'text.primary', mb: 1.5 }}>
        {children}
    </Typography>
);

export default function Footer() {
    return (
        <Box component="footer" sx={{ py: {xs: 4, md: 6}, mt: 'auto', backgroundColor: 'background.paper', borderTop: 1, borderColor: 'divider' }}>
            <Container maxWidth="lg">
                <Grid container spacing={4}>
                    <Grid item xs={12} md={5}>
                        <Stack spacing={2} alignItems={{xs: 'center', md: 'flex-start'}}>
                            <Stack direction="row" alignItems="center" spacing={1.5}>
                                <TrackChangesIcon color="primary" sx={{ fontSize: '2.5rem' }} />
                                <Typography variant="h5" sx={{ color: 'text.primary', fontWeight: 700 }}>
                                    {content.appName}
                                </Typography>
                            </Stack>
                            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 350, textAlign: {xs: 'center', md: 'left'} }}>
                                Интеллектуальная платформа для автоматизации и органического роста вашего профиля ВКонтакте.
                            </Typography>
                        </Stack>
                    </Grid>
                    <Grid item xs={6} md={3}>
                         <Stack spacing={1.5} alignItems={{xs: 'center', md: 'flex-start'}}>
                            <FooterTitle>Ресурсы</FooterTitle>
                            <FooterLink href="#">Политика конфиденциальности</FooterLink>
                            <FooterLink href="#">Условия использования</FooterLink>
                            <FooterLink href="#">База знаний</FooterLink>
                        </Stack>
                    </Grid>
                    <Grid item xs={6} md={4}>
                         <Stack spacing={1.5} alignItems={{xs: 'center', md: 'flex-start'}}>
                            <FooterTitle>Контакты</FooterTitle>
                            <FooterLink href="#">Техническая поддержка</FooterLink>
                        </Stack>
                    </Grid>
                </Grid>
                 <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', mt: {xs: 4, md: 6}, pt: 3, borderTop: 1, borderColor: 'divider' }}>
                    © {new Date().getFullYear()} {content.appName}. Все права защищены.
                </Typography>
            </Container>
        </Box>
    );
}

// --- frontend/src\components\Layout.js ---

// frontend/src/components/Layout.js
import React from 'react';
import {
    AppBar, Toolbar, Typography, Button, Container, Box, Stack,
    useTheme, useMediaQuery, IconButton, Drawer, List, ListItem, ListItemButton
} from '@mui/material';
import { Link as RouterLink, useLocation, Outlet } from 'react-router-dom';
import { useUserStore, useUserActions } from 'store/userStore';
// --- ИЗМЕНЕНИЕ: Иконка заменена на более стильную и подходящую ---
import HubIcon from '@mui/icons-material/Hub';
import MenuIcon from '@mui/icons-material/Menu';
import { content } from 'content/content';
import NotificationsBell from './NotificationsBell';
import Footer from './Footer';
// --- ИЗМЕНЕНИЕ: Импортируем хук для проверки тарифа ---
import { useFeatureFlag } from 'hooks/useFeatureFlag';

const navItems = [
    { label: content.nav.dashboard, to: "/dashboard", feature: null }, // Доступно всем
    { label: content.nav.scenarios, to: "/scenarios", feature: "scenarios" }, // Доступно по фиче
    { label: content.nav.billing, to: "/billing", feature: null }, // Доступно всем
];

const NavButton = ({ to, children }) => {
    const location = useLocation();
    const isActive = location.pathname === to;
    return (
        <Button
            component={RouterLink}
            to={to}
            sx={{
                fontWeight: 600,
                color: isActive ? 'text.primary' : 'text.secondary',
                position: 'relative',
                '&:after': {
                    content: '""',
                    position: 'absolute',
                    width: isActive ? '60%' : '0',
                    height: '2px',
                    bottom: '4px',
                    left: '20%',
                    backgroundColor: 'primary.main',
                    transition: 'width 0.3s ease-in-out',
                },
                '&:hover:after': {
                    width: '60%',
                },
                 '&:hover': {
                    color: 'text.primary',
                    backgroundColor: 'transparent'
                }
            }}
        >
            {children}
        </Button>
    );
};

const MobileDrawer = ({ open, onClose, onLogout, visibleNavItems }) => (
    <Drawer anchor="right" open={open} onClose={onClose} PaperProps={{ sx: { backgroundColor: 'background.default' }}}>
        <Box sx={{ width: 250, p: 2, height: '100%' }} role="presentation">
            <List>
                {visibleNavItems.map((item) => (
                    <ListItem key={item.label} disablePadding>
                        <ListItemButton component={RouterLink} to={item.to} onClick={onClose} sx={{ borderRadius: 2, mb: 1 }}>
                             <Typography variant="body1" fontWeight={600}>{item.label}</Typography>
                        </ListItemButton>
                    </ListItem>
                ))}
                 <ListItem disablePadding sx={{ mt: 3 }}>
                    <Button onClick={onLogout} fullWidth variant="outlined" color="error">{content.nav.logout}</Button>
                </ListItem>
            </List>
        </Box>
    </Drawer>
);


export default function Layout() {
    const jwtToken = useUserStore(state => state.jwtToken);
    const { logout } = useUserActions();
    // --- ИЗМЕНЕНИЕ: Получаем функцию проверки фич ---
    const { isFeatureAvailable } = useFeatureFlag();
    
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));
    const [drawerOpen, setDrawerOpen] = React.useState(false);

    // --- ИЗМЕНЕНИЕ: Фильтруем навигацию на основе тарифа пользователя ---
    const visibleNavItems = navItems.filter(item => !item.feature || isFeatureAvailable(item.feature));
    
    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
            <AppBar position="sticky" color="transparent" elevation={0} sx={{ backdropFilter: 'blur(10px)', backgroundColor: 'rgba(13, 14, 18, 0.7)', borderBottom: 1, borderColor: 'divider' }}>
                <Container maxWidth="xl">
                    <Toolbar sx={{ py: 1 }}>
                        <Stack direction="row" alignItems="center" spacing={1.5} component={RouterLink} to="/" sx={{textDecoration: 'none'}}>
                           <HubIcon color="primary" sx={{ fontSize: '2.5rem' }} />
                           <Typography variant="h5" sx={{ color: 'text.primary', fontWeight: 700, display: { xs: 'none', sm: 'block' } }}>
                                {content.appName}
                           </Typography>
                        </Stack>

                        <Box sx={{ flexGrow: 1 }} />

                        {isMobile ? (
                             <>
                                {jwtToken ? (
                                    <>
                                        <NotificationsBell />
                                        <IconButton onClick={() => setDrawerOpen(true)}><MenuIcon /></IconButton>
                                    </>
                                ) : (
                                    <Button component={RouterLink} to="/login" variant="contained">{content.nav.login}</Button>
                                )}
                             </>
                        ) : (
                            <Stack direction="row" spacing={1} alignItems="center">
                                {/* --- ИЗМЕНЕНИЕ: Отображаем только доступные пункты меню --- */}
                                {jwtToken && visibleNavItems.map(item => <NavButton key={item.to} to={item.to}>{item.label}</NavButton>)}
                                {jwtToken ? (
                                    <>
                                        <NotificationsBell />
                                        <Button onClick={logout} variant="outlined" color="primary" sx={{ ml: 2 }}>{content.nav.logout}</Button>
                                    </>
                                ) : (
                                    <Button component={RouterLink} to="/login" variant="contained" disableElevation>
                                        {content.nav.login}
                                    </Button>
                                )}
                            </Stack>
                        )}
                    </Toolbar>
                </Container>
            </AppBar>
            
            {isMobile && jwtToken && <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onLogout={() => { setDrawerOpen(false); logout(); }} visibleNavItems={visibleNavItems} />}

            <Box component="main" sx={{ flexGrow: 1 }}>
                 <Outlet />
            </Box>

            <Footer />
        </Box>
    );
}

// --- frontend/src\components\LazyLoader.js ---

// frontend/src/components/LazyLoader.js
import React from 'react';
import { Box, CircularProgress, Skeleton } from '@mui/material';

// Можно выбрать один из вариантов или комбинировать
const LazyLoader = ({ variant = 'circular' }) => {
    if (variant === 'skeleton') {
        return <Skeleton variant="rectangular" width="100%" height="100%" sx={{ borderRadius: 4 }} />;
    }

    return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', width: '100%', height: '100%' }}>
            <CircularProgress />
        </Box>
    );
};

export default LazyLoader;

// --- frontend/src\components\NotificationsBell.js ---

// frontend/src/components/NotificationsBell.js (ЗНАЧИТЕЛЬНЫЕ ИЗМЕНЕНИЯ)
import React, { useState } from 'react';
import {
    IconButton, Badge, Popover, List, ListItem, ListItemText,
    Typography, Box, CircularProgress, Divider, Avatar, ListItemAvatar, alpha
} from '@mui/material';
import NotificationsIcon from '@mui/icons-material/Notifications';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchNotifications, markNotificationsAsRead } from 'api';
import { formatDistanceToNow } from 'date-fns';
import { ru } from 'date-fns/locale';

const levelConfig = {
    error: { color: 'error', icon: <ErrorOutlineIcon /> },
    warning: { color: 'warning', icon: <InfoOutlinedIcon /> },
    success: { color: 'success', icon: <CheckCircleOutlineIcon /> },
    info: { color: 'info', icon: <InfoOutlinedIcon /> },
};

function NotificationItem({ notification }) {
    const config = levelConfig[notification.level] || levelConfig.info;

    return (
        <ListItem 
            alignItems="flex-start" 
            sx={{ 
                bgcolor: notification.is_read ? 'transparent' : (theme) => alpha(theme.palette[config.color].main, 0.1),
                transition: 'background-color 0.3s',
                '&:hover': {
                    bgcolor: (theme) => alpha(theme.palette.text.primary, 0.05)
                }
            }}
        >
            <ListItemAvatar sx={{ minWidth: 40, mt: 0.5 }}>
                <Avatar sx={{ bgcolor: `${config.color}.main`, width: 32, height: 32 }}>
                    {config.icon}
                </Avatar>
            </ListItemAvatar>
            <ListItemText
                primary={
                    <Typography variant="body2" sx={{ fontWeight: notification.is_read ? 400 : 500, color: 'text.primary' }}>
                        {notification.message}
                    </Typography>
                }
                secondary={
                    <Typography component="span" variant="caption" sx={{ color: `${config.color}.light` }}>
                        {formatDistanceToNow(new Date(notification.created_at), { addSuffix: true, locale: ru })}
                    </Typography>
                }
            />
        </ListItem>
    );
}

export default function NotificationsBell() {
    const [anchorEl, setAnchorEl] = useState(null);
    const queryClient = useQueryClient();

    const { data, isLoading } = useQuery({
        queryKey: ['notifications'],
        queryFn: fetchNotifications,
    });

    const mutation = useMutation({
        mutationFn: markNotificationsAsRead,
        onSuccess: () => {
            queryClient.setQueryData(['notifications'], (oldData) => {
                if (!oldData) return oldData;
                return {
                    ...oldData,
                    unread_count: 0,
                    items: oldData.items.map(item => ({ ...item, is_read: true })),
                };
            });
        },
    });

    const handleClick = (event) => {
        setAnchorEl(event.currentTarget);
        if (data?.unread_count > 0) {
            mutation.mutate();
        }
    };

    const handleClose = () => {
        setAnchorEl(null);
    };

    const open = Boolean(anchorEl);
    const id = open ? 'notifications-popover' : undefined;

    return (
        <>
            <IconButton color="inherit" onClick={handleClick}>
                <Badge badgeContent={data?.unread_count || 0} color="error">
                    <NotificationsIcon />
                </Badge>
            </IconButton>
            <Popover
                id={id}
                open={open}
                anchorEl={anchorEl}
                onClose={handleClose}
                // --- ИЗМЕНЕНИЕ: Позиционирование ближе к краю и стилизация ---
                anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
                transformOrigin={{ vertical: 'top', horizontal: 'right' }}
                slotProps={{ paper: { sx: { 
                    width: 380, 
                    maxHeight: 500, 
                    display: 'flex', 
                    flexDirection: 'column', 
                    borderRadius: 3, 
                    mt: 1.5,
                    // --- ИЗМЕНЕНИЕ: Добавляем полупрозрачность и размытие фона ---
                    backgroundColor: 'rgba(22, 22, 24, 0.8)',
                    backdropFilter: 'blur(10px)',
                } } }}
            >
                <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
                    <Typography variant="h6" component="div">Уведомления</Typography>
                </Box>
                
                {isLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
                ) : (
                    <List sx={{ p: 0, overflow: 'auto' }}>
                        {data?.items?.length > 0 ? (
                            data.items.map((notif, index) => (
                                <React.Fragment key={notif.id}>
                                    <NotificationItem notification={notif} />
                                    {index < data.items.length - 1 && <Divider component="li" variant="inset" />}
                                </React.Fragment>
                            ))
                        ) : (
                            <Typography sx={{ p: 3, textAlign: 'center', color: 'text.secondary' }}>
                                Здесь пока пусто
                            </Typography>
                        )}
                    </List>
                )}
            </Popover>
        </>
    );
}

// --- frontend/src\components\StatCard.js ---

// frontend/src/components/StatCard.js
import React from 'react';
import { Paper, Typography, Box, Skeleton, alpha } from '@mui/material';
import { motion } from 'framer-motion';

const StatCard = ({ title, value, icon, isLoading, color = 'primary' }) => {
    return (
        <motion.div whileHover={{ y: -5 }} transition={{ type: 'spring', stiffness: 300 }}>
            <Paper 
                sx={{ 
                    p: 2.5, 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: 3,
                    height: '100%',
                    position: 'relative',
                    overflow: 'hidden',
                    // --- ИЗМЕНЕНИЕ: Более стильный градиентный фон ---
                    background: (theme) => `linear-gradient(135deg, ${alpha(theme.palette[color].dark, 0.15)} 0%, ${alpha(theme.palette.background.paper, 0.15)} 100%)`,
                    borderColor: (theme) => alpha(theme.palette[color].main, 0.3),
                }}
            >
                {/* --- ИЗМЕНЕНИЕ: Иконка как большая вотермарка на фоне --- */}
                <Box sx={{ 
                    position: 'absolute',
                    right: -20,
                    bottom: -20,
                    color: `${color}.main`, 
                    fontSize: '120px',
                    opacity: 0.05,
                    transform: 'rotate(-20deg)',
                    pointerEvents: 'none',
                }}>
                    {icon}
                </Box>

                <Box>
                    <Typography variant="body1" color="text.secondary" sx={{ fontWeight: 500 }}>
                        {title}
                    </Typography>
                    {isLoading ? (
                        <Skeleton variant="text" width={80} height={40} />
                    ) : (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} key={value}>
                            <Typography variant="h4" sx={{ fontWeight: 700, mt: 0.5 }}>
                                {value?.toLocaleString('ru-RU') || 0}
                            </Typography>
                        </motion.div>
                    )}
                </Box>
            </Paper>
        </motion.div>
    );
};

export default StatCard;

// --- frontend/src\content\content.js ---

// frontend/src/content/content.js
import React from 'react';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import RecommendIcon from '@mui/icons-material/Recommend';
import HistoryIcon from '@mui/icons-material/History';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';
import FavoriteIcon from '@mui/icons-material/Favorite';
import CakeIcon from '@mui/icons-material/Cake';
import SendIcon from '@mui/icons-material/Send';
import OnlinePredictionIcon from '@mui/icons-material/OnlinePrediction';

export const content = {
    appName: "Zenith",
    nav: {
        dashboard: "Кабинет",
        scenarios: "Сценарии",
        billing: "Тарифы",
        login: "Войти",
        logout: "Выйти",
    },
    actions: {
        'accept_friends': { icon: <GroupAddIcon />, title: 'Прием заявок', modalTitle: "Прием входящих заявок" },
        'like_feed': { icon: <ThumbUpIcon />, title: 'Лайки в ленте', modalTitle: "Лайки в ленте новостей" },
        'add_recommended': { icon: <RecommendIcon />, title: 'Добавить друзей', modalTitle: "Добавление друзей из рекомендаций" },
        'like_friends_feed': { icon: <FavoriteIcon />, title: 'Лайки друзьям', modalTitle: "Лайки на посты друзей" },
        'view_stories': { icon: <HistoryIcon />, title: 'Просмотр историй', modalTitle: "Просмотр историй" },
        'remove_friends': { icon: <PersonRemoveIcon />, title: 'Чистка друзей', modalTitle: "Чистка списка друзей" },
        'mass_messaging': { icon: <SendIcon />, title: 'Массовая рассылка', modalTitle: "Массовая рассылка друзьям" },
    },
    automations: [
        { id: "like_feed", icon: <ThumbUpIcon />, name: "Авто-лайки в ленте", description: "Проставляет лайки на посты в ленте новостей." },
        { id: "add_recommended", icon: <RecommendIcon />, name: "Авто-добавление друзей", description: "Отправляет заявки пользователям из списка рекомендаций." },
        { id: "birthday_congratulation", icon: <CakeIcon />, name: "Авто-поздравления", description: "Поздравляет ваших друзей с Днем Рождения." },
        { id: "accept_friends", icon: <GroupAddIcon />, name: "Авто-прием заявок", description: "Принимает входящие заявки в друзья по вашим фильтрам." },
        { id: "remove_friends", icon: <PersonRemoveIcon />, name: "Авто-чистка друзей", description: "Удаляет неактивных и забаненных друзей." },
        { id: "view_stories", icon: <HistoryIcon />, name: "Авто-просмотр историй", description: "Просматривает все доступные истории друзей." },
        { id: "like_friends_feed", icon: <FavoriteIcon />, name: "Авто-лайки друзьям", description: "Проявляет активность, ставя лайки на посты друзей." },
        { id: "mass_messaging", icon: <SendIcon />, name: "Авто-рассылка", description: "Отправляет сообщения друзьям по заданным критериям." },
        { id: "eternal_online", icon: <OnlinePredictionIcon />, name: "Вечный онлайн", description: "Поддерживает статус 'онлайн' для вашего аккаунта." },
    ],
    loginPage: {
        title: "Добро пожаловать в Zenith",
        subtitle: "Ваш интеллектуальный ассистент для ВКонтакте",
        textFieldLabel: "Вставьте ключ доступа VK",
        buttonText: "Войти",
        tooltip: {
            step1: `1. Перейдите на сайт, нажав на <a href="https://vfeed.ru/v/token" target="_blank" rel="noopener noreferrer" style="color: #00BAE2; font-weight: 600;">эту ссылку</a>.`,
            step2: `2. Выберите "Windows Phone" или "Android" и разрешите доступ.`,
            step3: `3. Скопируйте ВСЮ ссылку из адресной строки браузера и вставьте в поле ниже.`
        },
        errors: {
            emptyToken: "Пожалуйста, вставьте ссылку или токен.",
            invalidUrl: "Некорректная ссылка. Скопируйте её полностью из адресной строки.",
            default: "Ошибка авторизации. Проверьте токен или убедитесь, что он не истек."
        }
    },
    modal: {
        launchButton: "Запустить",
        saveButton: "Сохранить",
        cancelButton: "Отмена",
        filtersTitle: "Критерии и фильтры",
        likeAfterRequest: {
            label: "Лайк после заявки",
            tooltip: "Автоматически ставить лайк на аватар пользователя после отправки заявки. Работает только для открытых профилей.",
        },
        messageOnAdd: {
            label: "Сообщение при добавлении",
            tooltip: "Отправить приветственное сообщение вместе с заявкой в друзья.",
            helperText: "Используйте {name} для подстановки имени."
        },
        massMessage: {
            onlyNewDialogsLabel: "Только новые диалоги",
            tooltip: "Отправить сообщение только тем друзьям, с которыми у вас еще нет начатой переписки."
        }
    }
};

// --- frontend/src\hooks\useActionModalState.js ---

// frontend/src/hooks/useActionModalState.js
import { useState, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchTaskInfo } from 'api.js';
import { useUserStore } from 'store/userStore';

export const useActionModalState = (open, actionKey, title) => {
    const [params, setParams] = useState({});
    const daily_add_friends_limit = useUserStore(state => state.userInfo?.daily_add_friends_limit);
    const daily_likes_limit = useUserStore(state => state.userInfo?.daily_likes_limit);

    const { data: taskInfo, isLoading: isLoadingInfo } = useQuery({
        queryKey: ['taskInfo', actionKey],
        queryFn: () => fetchTaskInfo(actionKey),
        enabled: !!(open && actionKey),
        staleTime: 1000 * 60 * 5,
    });

    useEffect(() => {
        if (open) {
            const defaults = {
                count: 50,
                filters: { sex: 0, is_online: false, allow_closed_profiles: false, remove_banned: true, min_friends: null, max_friends: null, min_followers: null, max_followers: null, last_seen_hours: 0, last_seen_days: 0 },
                like_config: { enabled: false, targets: ['avatar'] },
                send_message_on_add: false,
                message_text: "Привет, {name}! Увидел(а) твой профиль в рекомендациях, буду рад(а) знакомству.",
                only_new_dialogs: false,
            };
            if (actionKey === 'add_recommended') defaults.count = 20;
            if (actionKey === 'remove_friends') defaults.count = 500;
            setParams(defaults);
        }
    }, [open, actionKey]);
    
    const handleParamChange = useCallback((name, value) => {
        setParams(p => {
            const keys = name.split('.');
            if (keys.length > 1) {
                const newParams = { ...p };
                let current = newParams;
                for (let i = 0; i < keys.length - 1; i++) {
                    current[keys[i]] = { ...current[keys[i]] };
                    current = current[keys[i]];
                }
                current[keys[keys.length - 1]] = value;
                return newParams;
            }
            return { ...p, [name]: value };
        });
    }, []);
    
    const getModalTitle = useCallback(() => {
        let fullTitle = title;
        if (isLoadingInfo) {
            fullTitle += ' (Загрузка...)';
        } else if (taskInfo?.count !== undefined) {
            if (actionKey === 'accept_friends') fullTitle += ` (${taskInfo.count} заявок)`;
            if (actionKey === 'remove_friends') fullTitle += ` (${taskInfo.count} друзей)`;
        }
        return fullTitle;
    }, [title, actionKey, taskInfo, isLoadingInfo]);

    const getActionLimit = useCallback(() => {
        if (actionKey?.includes('add')) return daily_add_friends_limit || 100;
        if (actionKey?.includes('like')) return daily_likes_limit || 1000;
        if (actionKey === 'remove_friends') return taskInfo?.count || 1000;
        if (actionKey === 'mass_messaging') return 500;
        return 1000;
    }, [actionKey, daily_add_friends_limit, daily_likes_limit, taskInfo]);

    return { params, getModalTitle, handleParamChange, getActionLimit };
};

// --- frontend/src\hooks\useDashboardManager.js ---

// frontend/src/hooks/useDashboardManager.js
import { useState, useCallback } from 'react';
import { toast } from 'react-hot-toast';
import { runTask } from 'api.js';

const getErrorMessage = (error) => {
    if (typeof error?.response?.data?.detail === 'string') {
        return error.response.data.detail;
    }
    // --- ИЗМЕНЕНИЕ: Добавлена проверка на ошибки валидации ---
    if (Array.isArray(error.response?.data?.detail)) {
        // Берем первую ошибку валидации для простоты
        const firstError = error.response.data.detail[0];
        return `Ошибка валидации: ${firstError.loc.join('.')} - ${firstError.msg}`;
    }
    return error?.message || "Произошла неизвестная ошибка.";
};

// --- НОВАЯ ФУНКЦИЯ-ХЕЛПЕР ---
// Эта функция преобразует параметры в формат, который ожидает API.
const cleanupParams = (params) => {
    // Создаем глубокую копию, чтобы не изменять оригинальный стейт
    const cleaned = JSON.parse(JSON.stringify(params));

    if (cleaned.filters) {
        // Если для фильтра "last_seen_hours" установлено значение 0 ("Неважно"),
        // мы устанавливаем его в null, как того требует Pydantic-схема на бэкенде.
        if (cleaned.filters.last_seen_hours === 0) {
            cleaned.filters.last_seen_hours = null;
        }
        // То же самое для "last_seen_days".
        if (cleaned.filters.last_seen_days === 0) {
            cleaned.filters.last_seen_days = null;
        }
    }
    return cleaned;
};


export const useDashboardManager = () => {
    const [modalState, setModalState] = useState({ open: false, title: '', actionKey: '' });

    const openModal = useCallback((key, title) => {
        setModalState({ open: true, actionKey: key, title: title });
    }, []);
    
    const closeModal = useCallback(() => {
        setModalState({ open: false, title: '', actionKey: '' });
    }, []);

    const handleActionSubmit = useCallback(async (actionKey, params) => {
        const currentTitle = modalState.title; 
        const toastId = `task-queue-${actionKey}`;
        
        try {
            // --- ИЗМЕНЕНИЕ: Очищаем параметры перед отправкой ---
            const apiParams = cleanupParams(params);
            
            toast.loading(`Задача "${currentTitle}" добавляется в очередь...`, { id: toastId });
            await runTask(actionKey, apiParams); // Отправляем очищенные параметры
            toast.success(`Задача "${currentTitle}" успешно добавлена в очередь!`, { id: toastId });
        } catch (error) {
            const errorMessage = getErrorMessage(error);
            toast.error(errorMessage, { id: toastId });
        }
    }, [modalState.title]);

    return {
        modalState,
        openModal,
        closeModal,
        onActionSubmit: handleActionSubmit,
    };
};

// --- frontend/src\hooks\useFeatureFlag.js ---

// frontend/src/hooks/useFeatureFlag.js
import { useUserStore } from 'store/userStore';

/**
 * Хук для проверки доступности фич на основе данных, полученных с бэкенда.
 * @returns {{isFeatureAvailable: (featureKey: string) => boolean}}
 */
export const useFeatureFlag = () => {
    const availableFeatures = useUserStore(state => state.availableFeatures);

    const isFeatureAvailable = (featureKey) => {
        return availableFeatures.includes(featureKey);
    };

    return { isFeatureAvailable };
};

// --- frontend/src\pages\Billing\BillingPage.js ---

// frontend/src/pages/Billing/BillingPage.js
import React, { useState } from 'react';
import { Container, Typography, Grid, Skeleton, Stack, ToggleButtonGroup, ToggleButton } from '@mui/material';
import { motion } from 'framer-motion';
import { useUserStore } from 'store/userStore';
import { createPayment, fetchAvailablePlans } from 'api.js';
import { toast } from 'react-hot-toast';
import { useQuery } from '@tanstack/react-query';
import PlanCard from './components/PlanCard';

// --- ИЗМЕНЕНИЕ: Выносим опции периодов для удобства ---
const periodOptions = [
    { months: 1, label: '1 месяц' },
    { months: 3, label: '3 месяца' },
    { months: 6, label: '6 месяцев' },
    { months: 12, label: '1 год' },
];

export default function BillingPage() {
    const userInfo = useUserStore((state) => state.userInfo);
    const [loadingPlan, setLoadingPlan] = useState(null);
    // --- ИЗМЕНЕНИЕ: Состояние теперь хранит количество месяцев ---
    const [selectedMonths, setSelectedMonths] = useState(1);

    const { data: plansData, isLoading } = useQuery({ queryKey: ['plans'], queryFn: fetchAvailablePlans });
    
    // --- ИЗМЕНЕНИЕ: Функция теперь использует selectedMonths из состояния ---
    const handleChoosePlan = async (planId) => {
        setLoadingPlan(planId);
        try {
            const response = await createPayment(planId, selectedMonths);
            window.location.href = response.confirmation_url;
        } catch (error) {
            toast.error("Не удалось создать платеж. Пожалуйста, попробуйте позже.");
        } finally {
            setLoadingPlan(null);
        }
    };
    
    const handlePeriodChange = (event, newPeriod) => {
        if (newPeriod !== null) {
            setSelectedMonths(newPeriod);
        }
    };

    const containerVariants = { hidden: { opacity: 0 }, visible: { opacity: 1, transition: { staggerChildren: 0.1 } } };
    const itemVariants = { hidden: { opacity: 0, y: 30 }, visible: { opacity: 1, y: 0 } };

    return (
        <Container maxWidth="lg" sx={{ py: { xs: 4, md: 8 } }}>
            <motion.div initial="hidden" animate="visible" variants={containerVariants}>
                <motion.div variants={itemVariants}>
                    <Typography variant="h3" component="h1" textAlign="center" gutterBottom sx={{fontWeight: 700}}>Прозрачные тарифы для вашего роста</Typography>
                </motion.div>
                <motion.div variants={itemVariants}>
                    <Typography variant="h6" color="text.secondary" textAlign="center" sx={{ mb: 6, maxWidth: '700px', mx: 'auto' }}>Инвестируйте в автоматизацию, чтобы сосредоточиться на том, что действительно важно — на создании контента.</Typography>
                </motion.div>

                {/* --- ИЗМЕНЕНИЕ: ToggleButton для выбора периода --- */}
                <motion.div variants={itemVariants}>
                     <Stack alignItems="center" sx={{mb: 8}}>
                        <ToggleButtonGroup value={selectedMonths} exclusive onChange={handlePeriodChange} aria-label="billing period">
                            {periodOptions.map(opt => (
                                <ToggleButton key={opt.months} value={opt.months} sx={{px: 3, py: 1}}>
                                    {opt.label}
                                </ToggleButton>
                            ))}
                        </ToggleButtonGroup>
                    </Stack>
                </motion.div>
            </motion.div>
            
            <Grid container spacing={{ xs: 3, md: 4 }} alignItems="stretch" justifyContent="center">
                {isLoading ? (
                    Array.from(new Array(3)).map((_, index) => (
                       <Grid item xs={12} md={4} key={index}> <Skeleton variant="rounded" height={600} sx={{ borderRadius: 4 }} /> </Grid>
                    ))
                ) : (
                    plansData?.plans.map((plan) => (
                        <Grid item xs={12} md={4} key={plan.id}
                            component={motion.div} variants={itemVariants}
                            sx={{ zIndex: plan.is_popular ? 2 : 1, transform: plan.is_popular ? { xs: 'none', md: 'scale(1.05)' } : 'none' }}
                        >
                            <PlanCard
                                plan={plan}
                                isCurrent={plan.id === userInfo?.plan && userInfo?.is_plan_active}
                                onChoose={() => handleChoosePlan(plan.id)} 
                                isLoading={loadingPlan === plan.id}
                                selectedMonths={selectedMonths}
                                // --- ИЗМЕНЕНИЕ: Передаем информацию о скидке в дочерний компонент ---
                                periodInfo={plan.periods?.find(p => p.months === selectedMonths)}
                            />
                        </Grid>
                    ))
                )}
            </Grid>
        </Container>
    );
}

// --- frontend/src\pages\Billing\components\PlanCard.js ---

// frontend/src/pages/Billing/components/PlanCard.js
import React from 'react';
import { Paper, Button, Box, Chip, List, ListItem, ListItemIcon, Divider, CircularProgress, Typography, Stack, alpha } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import StarIcon from '@mui/icons-material/Star';

// --- ИЗМЕНЕНИЕ: Добавляем уникальные иконки для каждого тарифа ---
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import RocketLaunchOutlinedIcon from '@mui/icons-material/RocketLaunchOutlined';
import DiamondOutlinedIcon from '@mui/icons-material/DiamondOutlined';

// --- ИЗМЕНЕНИЕ: Компонент теперь принимает selectedMonths и periodInfo для динамического рендера ---
const PlanCard = ({ plan, isCurrent, onChoose, isLoading, selectedMonths, periodInfo }) => {

    // --- ИЗМЕНЕНИЕ: Логика расчета финальной цены с учетом скидки ---
    const finalPrice = plan.price === 0 ? 0 : Math.round(plan.price * selectedMonths * (1 - (periodInfo?.discount_percent || 0) / 100));
    const pricePerMonth = finalPrice > 0 ? Math.round(finalPrice / selectedMonths) : 0;

    const planMeta = {
        "Базовый": { icon: <AutoAwesomeOutlinedIcon />, color: 'info' },
        "Plus": { icon: <RocketLaunchOutlinedIcon />, color: 'primary' },
        "PRO": { icon: <DiamondOutlinedIcon />, color: 'secondary' }
    };
    const meta = planMeta[plan.display_name] || { icon: <StarIcon />, color: 'primary' };

    return (
        <Paper
          sx={{
            p: 4, display: 'flex', flexDirection: 'column', height: '100%',
            position: 'relative', overflow: 'hidden',
            boxShadow: plan.is_popular ? (theme) => `0 16px 48px -16px ${alpha(theme.palette[meta.color].main, 0.4)}` : 'inherit',
            // --- ИЗМЕНЕНИЕ: Стильная обводка для популярных и текущих тарифов ---
            '&:before': {
                content: '""', position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                borderRadius: 'inherit', padding: '2px',
                background: isCurrent ? (t) => `linear-gradient(45deg, ${t.palette.success.main}, ${t.palette.success.dark})`
                          : plan.is_popular ? (t) => `linear-gradient(45deg, ${t.palette[meta.color].main}, ${t.palette[meta.color].dark})`
                          : 'transparent',
                WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
                WebkitMaskComposite: 'xor', maskComposite: 'exclude', pointerEvents: 'none',
            },
          }}>
            {plan.is_popular && <Chip icon={<StarIcon />} label="Рекомендуем" color={meta.color} size="small" sx={{ position: 'absolute', top: 16, right: 16 }} />}
            
            <Stack direction="row" spacing={2} alignItems="center" sx={{mb: 2}}>
                <Box sx={{ color: `${meta.color}.main`, fontSize: '2.5rem' }}>{meta.icon}</Box>
                <Typography variant="h5" component="h2" sx={{ fontWeight: 700 }}>{plan.display_name}</Typography>
            </Stack>
            
            <Typography variant="body2" color="text.secondary" sx={{ minHeight: '40px' }}>{plan.description}</Typography>
            
            <Box sx={{ my: 3, display: 'flex', alignItems: 'flex-end', gap: 1 }}>
                <Typography variant="h3" component="p" sx={{ fontWeight: 700, lineHeight: 1 }}>
                    {finalPrice > 0 ? finalPrice.toLocaleString('ru-RU') : "Бесплатно"}
                </Typography>
                 {finalPrice > 0 && <Typography variant="h6" component="span" color="text.secondary">₽</Typography>}
            </Box>
            
            {/* --- ИЗМЕНЕНИЕ: Динамический показ скидки и цены за месяц --- */}
            <Stack direction="row" spacing={1} alignItems="center" sx={{minHeight: 40}}>
                {selectedMonths > 1 && plan.price > 0 && <Chip label={`~${pricePerMonth.toLocaleString('ru-RU')} ₽ / мес.`} size="small" />}
                {periodInfo?.discount_percent > 0 && <Chip label={`Выгода ${periodInfo.discount_percent}%`} color="success" variant="outlined" size="small" />}
            </Stack>
            
            <Divider sx={{ my: 2 }} />
            <Box sx={{ my: 2, flexGrow: 1 }}>
                <List sx={{ p: 0 }}>
                    {plan.features?.map((feature, index) => (
                        <ListItem key={index} disablePadding sx={{ mb: 1.5 }}>
                            <ListItemIcon sx={{ minWidth: '32px' }}><CheckIcon color={isCurrent ? 'success' : meta.color} fontSize="small"/></ListItemIcon>
                            <Typography variant="body1">{feature}</Typography>
                        </ListItem>
                    ))}
                </List>
            </Box>
            <Button
                variant={isCurrent ? 'outlined' : (plan.is_popular ? 'contained' : 'outlined')}
                size="large" fullWidth disabled={isCurrent || isLoading || plan.price === 0}
                onClick={() => onChoose(plan.id)}
                sx={{ mt: 'auto', minHeight: 48 }} color={isCurrent ? 'success' : meta.color}>
                {isLoading ? <CircularProgress size={24} color="inherit" /> : (isCurrent ? "Ваш текущий план" : "Выбрать")}
            </Button>
        </Paper>
    );
};

export default PlanCard;

// --- frontend/src\pages\Dashboard\DashboardPage.js ---

import React, { Suspense, useState, lazy, memo } from 'react';
import { Box, Paper, Link, Chip, Stack, Typography, Avatar, Grid, Button, Tooltip, Select, MenuItem, useTheme } from '@mui/material';
import { motion } from 'framer-motion';

// Hooks & State Management
import { useUserStore, useUserActions } from 'store/userStore';
import { useDashboardManager } from 'hooks/useDashboardManager';
import { useFeatureFlag } from 'hooks/useFeatureFlag';
import { useMutation } from '@tanstack/react-query';

// API & Utils
import { updateUserDelayProfile } from 'api';
import { toast } from 'react-hot-toast';

// Components
import LazyLoader from 'components/LazyLoader';
// --- ИЗМЕНЕНИЕ: Заменяем относительные пути на абсолютные для надежности ---
import ActionModal from 'pages/Dashboard/components/ActionModal';
import TaskLogWidget from 'pages/Dashboard/components/TaskLogWidget';
import ProfileSummaryWidget from 'pages/Dashboard/components/ProfileSummaryWidget';
import UnifiedActionPanel from 'pages/Dashboard/components/UnifiedActionPanel';

// Icons
import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import SpeedIcon from '@mui/icons-material/Speed';
import ShutterSpeedIcon from '@mui/icons-material/ShutterSpeed';
import SlowMotionVideoIcon from '@mui/icons-material/SlowMotionVideo';
import WifiIcon from '@mui/icons-material/Wifi';
import PowerSettingsNewIcon from '@mui/icons-material/PowerSettingsNew';

// --- ИЗМЕНЕНИЕ: Заменяем относительные пути на абсолютные в ленивых импортах ---
const ActivityChartWidget = lazy(() => import('pages/Dashboard/components/ActivityChartWidget'));
const AudienceAnalyticsWidget = lazy(() => import('pages/Dashboard/components/AudienceAnalyticsWidget'));
const ProfileGrowthWidget = lazy(() => import('pages/Dashboard/components/ProfileGrowthWidget'));
const ProxyManagerModal = lazy(() => import('pages/Dashboard/components/ProxyManagerModal'));
const AutomationSettingsModal = lazy(() => import('pages/Dashboard/components/AutomationSettingsModal'));

// Animation Variants
const motionVariants = {
    initial: { opacity: 0, y: 20 },
    animate: (i) => ({ opacity: 1, y: 0, transition: { delay: i * 0.1, duration: 0.5, ease: "easeOut" } }),
};

const UserProfileCard = memo(({ userInfo, connectionStatus, onProxyManagerOpen }) => {
    const theme = useTheme();
    const { isFeatureAvailable } = useFeatureFlag();
    const { setUserInfo } = useUserActions();
    const canUseProxyManager = isFeatureAvailable('proxy_management');
    const canChangeSpeed = isFeatureAvailable('fast_slow_delay_profile');

    const mutation = useMutation({
        mutationFn: updateUserDelayProfile,
        onSuccess: (response) => {
            setUserInfo(response.data);
            toast.success(`Скорость работы изменена!`);
        },
        onError: () => toast.error("Не удалось изменить скорость.")
    });

    const handleSpeedChange = (event) => {
        mutation.mutate({ delay_profile: event.target.value });
    };

    const isConnected = connectionStatus === 'На связи';

    return (
        <Paper sx={{ p: 3, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: 'center', gap: 3, height: '100%' }}>
            <Avatar src={userInfo.photo_200} sx={{ width: 100, height: 100, flexShrink: 0, border: '4px solid', borderColor: theme.palette.background.default, boxShadow: 3 }} />
            <Box flexGrow={1} width="100%">
                 <Stack direction="row" justifyContent="space-between" alignItems="flex-start" spacing={1} sx={{mb: 1.5}}>
                     <Link href={`https://vk.com/id${userInfo.vk_id}`} target="_blank" color="text.primary" sx={{ textDecoration: 'none' }}>
                        <Typography variant="h5" sx={{ fontWeight: 700, '&:hover': { color: 'primary.main' } }}>{userInfo.first_name} {userInfo.last_name}</Typography>
                    </Link>
                    <Chip 
                        label={connectionStatus} 
                        icon={isConnected ? <WifiIcon/> : <PowerSettingsNewIcon/>} 
                        color={isConnected ? 'success' : 'warning'} 
                        size="small" 
                        sx={{ flexShrink: 0, mt: 0.5 }} 
                    />
                </Stack>
                <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
                    <Chip icon={<WorkspacePremiumIcon />} label={userInfo.plan} color="primary" variant="filled" size="small"/>
                    {userInfo.plan_expires_at && <Typography variant="caption" color="text.secondary">До {new Date(userInfo.plan_expires_at).toLocaleDateString('ru-RU')}</Typography>}
                </Stack>
                <Grid container spacing={1} alignItems="center">
                    <Grid item xs={12} sm={6} md={4}>
                         <Tooltip title={canUseProxyManager ? "Управление прокси" : "Доступно на PRO-тарифе"}>
                            <span>
                                <Button fullWidth size="small" startIcon={<VpnKeyIcon />} onClick={onProxyManagerOpen} disabled={!canUseProxyManager} variant="outlined" sx={{color: 'text.secondary'}}>Прокси</Button>
                            </span>
                        </Tooltip>
                    </Grid>
                    <Grid item xs={12} sm={6} md={8}>
                        <Tooltip title={!canChangeSpeed ? "Смена скорости доступна на PRO-тарифе" : ""}>
                            <Select
                                fullWidth size="small" value={userInfo.delay_profile} onChange={handleSpeedChange} disabled={mutation.isLoading || !canChangeSpeed}
                                renderValue={(value) => (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        {value === 'fast' && <ShutterSpeedIcon fontSize="small" />}
                                        {value === 'normal' && <SpeedIcon fontSize="small" />}
                                        {value === 'slow' && <SlowMotionVideoIcon fontSize="small" />}
                                        {value === 'fast' && 'Быстрый'}
                                        {value === 'normal' && 'Стандарт'}
                                        {value === 'slow' && 'Медленный'}
                                    </Box>
                                )}>
                                <MenuItem value="slow"><SlowMotionVideoIcon sx={{mr: 1}}/> Медленный (Макс. безопасность)</MenuItem>
                                <MenuItem value="normal"><SpeedIcon sx={{mr: 1}}/> Стандарт (Баланс)</MenuItem>
                                <MenuItem value="fast"><ShutterSpeedIcon sx={{mr: 1}}/> Быстрый (Макс. скорость)</MenuItem>
                            </Select>
                        </Tooltip>
                    </Grid>
                </Grid>
            </Box>
        </Paper>
    );
});

export default function DashboardPage() {
    const userInfo = useUserStore(state => state.userInfo);
    const connectionStatus = useUserStore(state => state.connectionStatus);
    const { isFeatureAvailable } = useFeatureFlag();
    const { modalState, openModal, closeModal, onActionSubmit } = useDashboardManager();
    const [isProxyModalOpen, setProxyModalOpen] = useState(false);
    const [automationToEdit, setAutomationToEdit] = useState(null);

    if (!userInfo) {
        return <LazyLoader />;
    }

    return (
        <Box sx={{ py: 4, px: { xs: 1, sm: 2, lg: 3 } }}>
             <motion.div custom={0} variants={motionVariants} initial="initial" animate="animate">
                <Typography variant="h4" component="h1" sx={{ fontWeight: 700, mb: 3 }}>
                    Панель управления
                </Typography>
            </motion.div>
            
            <Grid container spacing={3}>
                {/* Левая колонка */}
                <Grid item xs={12} lg={4}>
                    <motion.div custom={1} variants={motionVariants} initial="initial" animate="animate" style={{ height: '100%' }}>
                       <UnifiedActionPanel onRun={openModal} onSettings={setAutomationToEdit} />
                    </motion.div>
                </Grid>
                
                {/* Правая колонка */}
                <Grid item xs={12} lg={8}>
                    <Stack spacing={3}>
                        <motion.div custom={2} variants={motionVariants} initial="initial" animate="animate">
                            <UserProfileCard userInfo={userInfo} connectionStatus={connectionStatus} onProxyManagerOpen={() => setProxyModalOpen(true)} />
                        </motion.div>
                         <motion.div custom={2.5} variants={motionVariants} initial="initial" animate="animate">
                             <Suspense fallback={<LazyLoader />}>
                                 <ProfileSummaryWidget />
                             </Suspense>
                         </motion.div>
                        <motion.div custom={3} variants={motionVariants} initial="initial" animate="animate">
                            <Suspense fallback={<LazyLoader />}>
                                <ActivityChartWidget />
                            </Suspense>
                        </motion.div>
                        {isFeatureAvailable('profile_growth_analytics') && (
                            <motion.div custom={4} variants={motionVariants} initial="initial" animate="animate">
                               <Suspense fallback={<LazyLoader />}>
                                    <ProfileGrowthWidget />
                               </Suspense>
                            </motion.div>
                        )}
                        <motion.div custom={5} variants={motionVariants} initial="initial" animate="animate">
                           <Suspense fallback={<LazyLoader />}>
                                <AudienceAnalyticsWidget />
                           </Suspense>
                        </motion.div>
                    </Stack>
                </Grid>

                {/* Нижний блок на всю ширину */}
                <Grid item xs={12}>
                    <motion.div custom={6} variants={motionVariants} initial="initial" animate="animate">
                         <TaskLogWidget />
                    </motion.div>
                </Grid>
            </Grid>
            
            <ActionModal {...modalState} onClose={closeModal} onSubmit={onActionSubmit} />
            <Suspense>
                {isProxyModalOpen && <ProxyManagerModal open={isProxyModalOpen} onClose={() => setProxyModalOpen(false)} />}
                {automationToEdit && <AutomationSettingsModal open={!!automationToEdit} onClose={() => setAutomationToEdit(null)} automation={automationToEdit} />}
            </Suspense>
        </Box>
    );
}

// --- frontend/src\pages\Dashboard\components\ActionModal.js ---

// frontend/src/pages/Dashboard/components/ActionModal.js
import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button } from '@mui/material';
import ActionModalContent from './ActionModalContent';
import { useActionModalState } from 'hooks/useActionModalState';
import { content } from 'content/content';

const ActionModal = ({ open, onClose, onSubmit, title, actionKey }) => {
    const { params, getModalTitle, handleParamChange, getActionLimit } = useActionModalState(open, actionKey, title);

    const handleSubmit = () => {
        onSubmit(actionKey, params);
        onClose();
    };
    
    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm" PaperProps={{ sx: { borderRadius: 4 } }}>
            <DialogTitle sx={{ fontWeight: 600, pb: 1 }}>{getModalTitle()}</DialogTitle>
            <DialogContent dividers>
                <ActionModalContent 
                    actionKey={actionKey}
                    params={params}
                    onParamChange={handleParamChange}
                    limit={getActionLimit()}
                />
            </DialogContent>
            <DialogActions sx={{ p: 2 }}>
                <Button onClick={onClose}>{content.modal.cancelButton}</Button>
                <Button onClick={handleSubmit} variant="contained">{content.modal.launchButton}</Button>
            </DialogActions>
        </Dialog>
    );
};

export default ActionModal;

// --- frontend/src\pages\Dashboard\components\ActionModalContent.js ---

// frontend/src/pages/Dashboard/components/ActionModalContent.js
import React from 'react';
import { TextField, Box, FormControlLabel, Switch, Divider, Tooltip, Stack } from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { content } from 'content/content';
import ActionModalFilters from './ActionModalFilters';
import CountSlider from 'components/CountSlider';


const { modal: modalContent } = content;

const LikeAfterAdd = ({ enabled, onChange }) => (
    <FormControlLabel
        control={<Switch checked={enabled} onChange={(e) => onChange('like_config.enabled', e.target.checked)} />}
        label={
            <Box display="flex" alignItems="center" component="span">
                {modalContent.likeAfterRequest.label}
                <Tooltip title={modalContent.likeAfterRequest.tooltip} placement="top" arrow>
                    <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
                </Tooltip>
            </Box>
        }
    />
);

const MessageOnAdd = ({ enabled, text, onChange }) => (
    <Stack spacing={1} sx={{mt: 2}}>
         <FormControlLabel
            control={<Switch checked={enabled} onChange={(e) => onChange('send_message_on_add', e.target.checked)} />}
            label={
                <Box display="flex" alignItems="center" component="span">
                    {modalContent.messageOnAdd.label}
                    <Tooltip title={modalContent.messageOnAdd.tooltip} placement="top" arrow>
                         <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
                    </Tooltip>
                </Box>
            }
        />
        {enabled && (
             <TextField
                fullWidth multiline rows={3}
                label="Текст сообщения"
                value={text} onChange={(e) => onChange('message_text', e.target.value)}
                helperText={modalContent.messageOnAdd.helperText}
            />
        )}
    </Stack>
);

const MassMessageSettings = ({ params, onChange }) => (
    <Stack spacing={2} sx={{mt: 2}}>
        <TextField
            fullWidth multiline rows={4}
            label="Текст сообщения"
            value={params.message_text || ''} onChange={(e) => onChange('message_text', e.target.value)}
            helperText={modalContent.messageOnAdd.helperText}
        />
        <FormControlLabel
            control={<Switch checked={params.only_new_dialogs || false} onChange={(e) => onChange('only_new_dialogs', e.target.checked)} />}
            label={
                <Box display="flex" alignItems="center" component="span">
                    {modalContent.massMessage.onlyNewDialogsLabel}
                    <Tooltip title={modalContent.massMessage.tooltip} placement="top" arrow>
                         <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
                    </Tooltip>
                </Box>
            }
        />
    </Stack>
);

const ActionModalContent = ({ actionKey, params, onParamChange, limit }) => {
    const actionConfig = content.actions[actionKey];
    if (!actionConfig) return null;

    const needsCount = !!actionConfig.modal_count_label;
    const hasFilters = !['view_stories'].includes(actionKey);
    
    return (
        <Stack spacing={3} py={1}>
            {/* --- ИЗМЕНЕНИЕ: Замена TextField на CountSlider --- */}
            {needsCount && (
                <CountSlider
                    label={actionConfig.modal_count_label}
                    value={params.count || 0}
                    onChange={(val) => onParamChange('count', val)}
                    max={limit}
                />
            )}
            
            {actionKey === 'add_recommended' && (
                <Box>
                    <LikeAfterAdd enabled={params.like_config?.enabled || false} onChange={onParamChange} />
                    <MessageOnAdd 
                        enabled={params.send_message_on_add || false}
                        text={params.message_text || ''}
                        onChange={onParamChange}
                    />
                </Box>
            )}

            {actionKey === 'mass_messaging' && (
                <MassMessageSettings params={params} onChange={onParamChange} />
            )}
            
            {hasFilters && (
                <>
                    <Divider />
                    <ActionModalFilters filters={params.filters || {}} onChange={onParamChange} actionKey={actionKey} />
                </>
            )}
        </Stack>
    );
};

export default ActionModalContent;

// --- frontend/src\pages\Dashboard\components\ActionModalFilters.js ---

// frontend/src/pages/Dashboard/components/ActionModalFilters.js
import React from 'react';
import {
    FormControlLabel, Switch, Select, MenuItem, InputLabel, FormControl, Grid, Typography, Box, Tooltip, TextField
} from '@mui/material';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import { content } from 'content/content';

const FilterWrapper = ({ children }) => (
    <Box>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>{content.modal.filtersTitle}</Typography>
        {children}
    </Box>
);

const LabelWithTooltip = ({ title, tooltipText }) => (
    <Box display="flex" alignItems="center" component="span">
        {title}
        <Tooltip title={tooltipText} placement="top" arrow>
            <InfoOutlinedIcon fontSize="small" color="secondary" sx={{ ml: 0.5, cursor: 'help' }} />
        </Tooltip>
    </Box>
);

export const CommonFiltersSettings = ({ filters, onChange, actionKey }) => {
    const showClosedProfilesFilter = ['accept_friends', 'add_recommended', 'mass_messaging'].includes(actionKey);
    const isAcceptFriends = actionKey === 'accept_friends';

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        const val = type === 'checkbox' ? checked : (type === 'number' ? (value ? parseInt(value, 10) : null) : value);
        onChange(name, val);
    };

    return (
        <FilterWrapper>
            <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} sm={6}>
                    <FormControlLabel control={<Switch name="is_online" checked={filters.is_online || false} onChange={handleChange} />} label="Только онлайн" />
                </Grid>
                {showClosedProfilesFilter && (
                    <Grid item xs={12} sm={6}>
                        <FormControlLabel
                            control={<Switch name="allow_closed_profiles" checked={filters.allow_closed_profiles || false} onChange={handleChange} />}
                            label={<LabelWithTooltip title="Закрытые профили" tooltipText="Разрешить взаимодействие с пользователями, у которых закрыт профиль." />}
                        />
                    </Grid>
                )}
                <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>Был(а) в сети</InputLabel>
                        <Select name="last_seen_hours" value={filters.last_seen_hours || 0} label="Был(а) в сети" onChange={handleChange}>
                            <MenuItem value={0}>Неважно</MenuItem>
                            <MenuItem value={1}>В течение часа</MenuItem>
                            <MenuItem value={3}>В течение 3 часов</MenuItem>
                            <MenuItem value={12}>В течение 12 часов</MenuItem>
                            <MenuItem value={24}>В течение суток</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
                <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>Пол</InputLabel>
                        <Select name="sex" value={filters.sex || 0} label="Пол" onChange={handleChange}>
                            <MenuItem value={0}>Любой</MenuItem>
                            <MenuItem value={1}>Женский</MenuItem>
                            <MenuItem value={2}>Мужской</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
                <Grid item xs={12}>
                    <TextField
                        name="status_keyword"
                        value={filters.status_keyword || ''}
                        onChange={handleChange}
                        label="Ключевое слово в статусе"
                        size="small"
                        fullWidth
                        placeholder="Например: ищу работу, спб"
                        helperText="Не применяется к закрытым профилям."
                    />
                </Grid>
                 {isAcceptFriends && (
                    <>
                        {/* --- ИЗМЕНЕНИЕ: Замена Select на TextField для гибкости --- */}
                        <Grid item xs={6}>
                           <TextField
                                name="min_friends"
                                value={filters.min_friends || ''}
                                onChange={handleChange}
                                label="Мин. друзей"
                                type="number"
                                size="small"
                                fullWidth
                                placeholder="Любое"
                           />
                        </Grid>
                         <Grid item xs={6}>
                           <TextField
                                name="max_friends"
                                value={filters.max_friends || ''}
                                onChange={handleChange}
                                label="Макс. друзей"
                                type="number"
                                size="small"
                                fullWidth
                                placeholder="Любое"
                           />
                        </Grid>
                         <Grid item xs={6}>
                           <TextField
                                name="min_followers"
                                value={filters.min_followers || ''}
                                onChange={handleChange}
                                label="Мин. подписчиков"
                                type="number"
                                size="small"
                                fullWidth
                                placeholder="Любое"
                           />
                        </Grid>
                         <Grid item xs={6}>
                            <TextField
                                name="max_followers"
                                value={filters.max_followers || ''}
                                onChange={handleChange}
                                label="Макс. подписчиков"
                                type="number"
                                size="small"
                                fullWidth
                                placeholder="Любое"
                           />
                        </Grid>
                    </>
                )}
            </Grid>
        </FilterWrapper>
    );
};

export const RemoveFriendsFilters = ({ filters, onChange }) => {
    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        const val = type === 'checkbox' ? checked : value;
        onChange(name, val);
    };
    return (
        <Box>
             <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>Критерии для чистки</Typography>
            <Grid container spacing={2} alignItems="center">
                 <Grid item xs={12}>
                    <FormControlLabel
                        control={<Switch name="remove_banned" checked={filters.remove_banned !== false} onChange={handleChange} />}
                        label={<LabelWithTooltip title="Удаленные / забаненные" tooltipText="Удалить пользователей, чьи страницы были удалены или заблокированы." />}
                    />
                </Grid>
                <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>Неактивные (не заходили более)</InputLabel>
                        <Select name="last_seen_days" value={filters.last_seen_days || 0} label="Неактивные (не заходили более)" onChange={handleChange}>
                           <MenuItem value={0}>Не удалять по неактивности</MenuItem>
                           <MenuItem value={30}>1 месяца</MenuItem>
                           <MenuItem value={90}>3 месяцев</MenuItem>
                           <MenuItem value={180}>6 месяцев</MenuItem>
                           <MenuItem value={365}>1 года</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
                 <Grid item xs={12}>
                    <FormControl fullWidth size="small">
                        <InputLabel>Пол</InputLabel>
                        <Select name="sex" value={filters.sex || 0} label="Пол" onChange={handleChange}>
                           <MenuItem value={0}>Любой</MenuItem>
                           <MenuItem value={1}>Женский</MenuItem>
                           <MenuItem value={2}>Мужской</MenuItem>
                        </Select>
                    </FormControl>
                </Grid>
            </Grid>
        </Box>
    );
};

export default function ActionModalFilters({ filters, onChange, actionKey }) {
    if (actionKey === 'remove_friends') {
        return <RemoveFriendsFilters filters={filters} onChange={(name, val) => onChange(`filters.${name}`, val)} />;
    }
    return <CommonFiltersSettings filters={filters} onChange={(name, val) => onChange(`filters.${name}`, val)} actionKey={actionKey} />;
}

// --- frontend/src\pages\Dashboard\components\ActionPanel.js ---

// frontend/src/pages/Dashboard/components/ActionPanel.js
import React from 'react';
import { Typography, Button, List, ListItem, ListItemText, ListItemIcon, Stack, Paper, alpha } from '@mui/material';
import { content } from 'content/content';
import { motion } from 'framer-motion';

export default function ActionPanel({ onConfigure }) {
  return (
    <Paper sx={{ p: 3, height: '100%' }}>
      <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
        Панель действий
      </Typography>
      <List sx={{ p: 0 }}>
        <Stack spacing={1.5}>
          {Object.entries(content.actions).map(([key, action]) => (
            <motion.div whileHover={{ scale: 1.03 }} transition={{ type: 'spring', stiffness: 400, damping: 10 }} key={key}>
                <ListItem
                  secondaryAction={
                    <Button edge="end" variant="contained" size="small" onClick={() => onConfigure(key, action.modalTitle)}>
                      Настроить
                    </Button>
                  }
                  sx={{
                    p: 2, borderRadius: 3,
                    bgcolor: 'background.default',
                    border: '1px solid', borderColor: 'divider',
                    display: 'flex', alignItems: 'center', gap: 2,
                    cursor: 'pointer',
                    '&:hover': {
                        borderColor: 'primary.main',
                        boxShadow: (theme) => `0 4px 16px ${alpha(theme.palette.primary.main, 0.2)}`,
                    },
                  }}
                  onClick={() => onConfigure(key, action.modalTitle)}
                >
                  <ListItemIcon sx={{ color: 'primary.main', minWidth: 'auto', mr: 0, fontSize: '2rem' }}>
                    {action.icon}
                  </ListItemIcon>
                  <ListItemText
                    primary={action.title}
                    sx={{
                      '& .MuiListItemText-primary': { fontWeight: 600 },
                      m: 0,
                    }}
                  />
                </ListItem>
            </motion.div>
          ))}
        </Stack>
      </List>
    </Paper>
  );
}

// --- frontend/src\pages\Dashboard\components\ActivityChartWidget.js ---

// frontend/src/pages/Dashboard/components/ActivityChartWidget.js
import React, { useState, useMemo } from 'react';
import { Paper, Typography, Box, useTheme, ButtonGroup, Button, Skeleton } from '@mui/material';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { fetchActivityStats } from 'api.js';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <Paper sx={{ p: 2, background: 'rgba(30, 31, 37, 0.9)', backdropFilter: 'blur(5px)', borderRadius: 2 }}>
                <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>{format(new Date(label), 'd MMMM yyyy', { locale: ru })}</Typography>
                {payload.map(p => (
                    <Typography key={p.name} variant="body2" sx={{ color: p.color }}>
                        {`${p.name}: ${p.value}`}
                    </Typography>
                ))}
            </Paper>
        );
    }
    return null;
};

export default function ActivityChartWidget() {
    const [days, setDays] = useState(7);
    const theme = useTheme();

    const { data: statsData, isLoading } = useQuery({
        queryKey: ['activityStats', days],
        queryFn: () => fetchActivityStats(days),
        placeholderData: (prev) => prev,
    });

    const series = useMemo(() => {
        return statsData?.data.map(item => ({
            date: new Date(item.date).getTime(),
            Лайки: item.likes,
            "Отправлено заявок": item.friends_added,
            "Принято заявок": item.requests_accepted
        })) || [];
    }, [statsData]);

    const renderContent = () => {
        if ((isLoading && !statsData) || !series) {
            return <Skeleton variant="rounded" height={280} />;
        }

        if (series.length === 0) {
            return <Box sx={{display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center'}}><Typography color="text.secondary">Нет данных для отображения.</Typography></Box>;
        }

        return (
            <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={series} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <defs>
                        <linearGradient id="colorLikes" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={theme.palette.primary.main} stopOpacity={0.8}/>
                            <stop offset="95%" stopColor={theme.palette.primary.main} stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={theme.palette.success.main} stopOpacity={0.8}/>
                            <stop offset="95%" stopColor={theme.palette.success.main} stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorAccepted" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={theme.palette.warning.main} stopOpacity={0.8}/>
                            <stop offset="95%" stopColor={theme.palette.warning.main} stopOpacity={0}/>
                        </linearGradient>
                    </defs>
                    <XAxis 
                        dataKey="date" 
                        stroke={theme.palette.text.secondary} 
                        tickFormatter={(timeStr) => format(new Date(timeStr), 'd MMM', { locale: ru })}
                        fontSize="0.8rem"
                    />
                    <YAxis stroke={theme.palette.text.secondary} fontSize="0.8rem" />
                    <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="Лайки" stroke={theme.palette.primary.main} fillOpacity={1} fill="url(#colorLikes)" strokeWidth={2} />
                    <Area type="monotone" dataKey="Отправлено заявок" stroke={theme.palette.success.main} fillOpacity={1} fill="url(#colorRequests)" strokeWidth={2} />
                    <Area type="monotone" dataKey="Принято заявок" stroke={theme.palette.warning.main} fillOpacity={1} fill="url(#colorAccepted)" strokeWidth={2} />
                </AreaChart>
            </ResponsiveContainer>
        );
    }

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>Статистика активности</Typography>
                <ButtonGroup size="small">
                    <Button variant={days === 7 ? 'contained' : 'outlined'} onClick={() => setDays(7)}>Неделя</Button>
                    <Button variant={days === 30 ? 'contained' : 'outlined'} onClick={() => setDays(30)}>Месяц</Button>
                </ButtonGroup>
            </Box>
            <Box sx={{ flexGrow: 1, minHeight: 280, position: 'relative' }}>
                {renderContent()}
            </Box>
        </Paper>
    );
}

// --- frontend/src\pages\Dashboard\components\AudienceAnalyticsWidget.js ---

// frontend/src/pages/Dashboard/components/AudienceAnalyticsWidget.js
import React, { useMemo } from 'react';
import { Paper, Typography, useTheme, Grid, Skeleton, Tooltip, IconButton, Stack, alpha, Box } from '@mui/material';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip as RechartsTooltip, PieChart, Pie, Cell, Legend } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { fetchAudienceAnalytics } from 'api.js';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <Paper sx={{ p: 2, background: 'rgba(30, 31, 37, 0.9)', backdropFilter: 'blur(5px)', borderRadius: 2 }}>
                <Typography variant="body2">{`${label}: ${payload[0].value.toLocaleString('ru-RU')}`}</Typography>
            </Paper>
        );
    }
    return null;
};

// --- ИЗМЕНЕНИЕ: Кастомная метка для PieChart, чтобы текст был внутри ---
const RADIAN = Math.PI / 180;
const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    if (percent < 0.05) return null; // Не показывать метку для очень маленьких секторов

    return (
        <text x={x} y={y} fill="white" textAnchor="middle" dominantBaseline="central" fontSize="0.9rem" fontWeight={600}>
            {`${(percent * 100).toFixed(0)}%`}
        </text>
    );
};

export default function AudienceAnalyticsWidget() {
    const theme = useTheme();
    const { data, isLoading, isError } = useQuery({ queryKey: ['audienceAnalytics'], queryFn: fetchAudienceAnalytics, staleTime: 1000 * 60 * 60 });

    const chartData = useMemo(() => {
        return {
            city: data?.city_distribution || [],
            age: data?.age_distribution || [],
            sex: data?.sex_distribution || [],
        };
    }, [data]);
    
    const COLORS = [theme.palette.primary.main, theme.palette.secondary.main, theme.palette.warning.main, theme.palette.success.main, theme.palette.info.main];

    const renderContent = () => {
        if (isLoading) return <Skeleton variant="rounded" height={250} />;
        if (isError) return <Typography color="error.main">Ошибка загрузки аналитики.</Typography>;
        if (!data || !data.sex_distribution || data.sex_distribution.length === 0) return <Box sx={{display: 'flex', height: 250, alignItems: 'center', justifyContent: 'center'}}><Typography color="text.secondary">Нет данных для анализа.</Typography></Box>;

        return (
            <Grid container spacing={3} alignItems="center">
                <Grid item xs={12} md={5}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, textAlign: 'center', mb: 1 }}>Пол</Typography>
                    <ResponsiveContainer width="100%" height={220}>
                        <PieChart>
                            {/* --- ИЗМЕНЕНИЕ: Используем кастомную метку --- */}
                            <Pie data={chartData.sex} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={100} labelLine={false} label={renderCustomizedLabel}>
                                {chartData.sex.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
                            </Pie>
                             <RechartsTooltip content={<CustomTooltip />} />
                            <Legend />
                        </PieChart>
                    </ResponsiveContainer>
                </Grid>
                 <Grid item xs={12} md={7}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, textAlign: 'center', mb: 1 }}>Топ городов</Typography>
                     <ResponsiveContainer width="100%" height={220}>
                        {/* --- ИЗМЕНЕНИЕ: Увеличен отступ слева для длинных названий --- */}
                        <BarChart data={chartData.city} layout="vertical" margin={{ top: 5, right: 20, left: 80, bottom: 5 }}>
                             <XAxis type="number" hide />
                             <YAxis type="category" dataKey="name" width={80} tick={{ fill: theme.palette.text.secondary, fontSize: '0.8rem' }} tickLine={false} axisLine={false} />
                             <RechartsTooltip content={<CustomTooltip />} cursor={{ fill: alpha(theme.palette.primary.main, 0.1) }}/>
                             <Bar dataKey="value" barSize={20} radius={[0, 8, 8, 0]}>
                                 {chartData.city.map((entry, index) => <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />)}
                             </Bar>
                         </BarChart>
                     </ResponsiveContainer>
                 </Grid>
            </Grid>
        );
    };

    return (
        <Paper sx={{ p: 3, height: '100%' }}>
             <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 600, m: 0 }}>Анализ аудитории</Typography>
                <Tooltip title="Анализ на основе ваших друзей. Данные периодически обновляются для поддержания актуальности." arrow>
                    <IconButton size="small"><InfoOutlinedIcon fontSize='small' /></IconButton>
                </Tooltip>
             </Stack>
            {renderContent()}
        </Paper>
    );
}

// --- frontend/src\pages\Dashboard\components\AutomationSettingsModal.js ---

// frontend/src/pages/Dashboard/components/AutomationSettingsModal.js
import React, { useState, useEffect } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, CircularProgress, Stack, Divider, Typography, ToggleButtonGroup, ToggleButton, RadioGroup, FormControlLabel, Radio } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { updateAutomation } from 'api';
import { CommonFiltersSettings, RemoveFriendsFilters } from './ActionModalFilters';
import CountSlider from 'components/CountSlider';
import { useUserStore } from 'store/userStore';
import { content } from 'content/content';

const EternalOnlineSettings = ({ settings, onChange }) => {
    const days = [
        { key: 0, label: 'Пн' }, { key: 1, label: 'Вт' }, { key: 2, label: 'Ср' },
        { key: 3, label: 'Чт' }, { key: 4, label: 'Пт' }, { key: 5, label: 'Сб' }, { key: 6, label: 'Вс' },
    ];

    const handleDaysChange = (event, newDays) => {
        onChange('days_of_week', newDays);
    };

    return (
        <Stack spacing={2}>
            <Typography variant="subtitle1" fontWeight={600}>Режим работы</Typography>
            <RadioGroup
                row
                value={settings.schedule_type || 'always'}
                onChange={(e) => onChange('schedule_type', e.target.value)}
            >
                <FormControlLabel value="always" control={<Radio />} label="Круглосуточно" />
                <FormControlLabel value="custom" control={<Radio />} label="По расписанию" />
            </RadioGroup>

            {settings.schedule_type === 'custom' && (
                <Stack spacing={2} p={2} borderRadius={2} border="1px solid" borderColor="divider">
                     <Typography variant="body2" color="text.secondary">Выберите дни и время (по МСК), когда статус "онлайн" будет активен.</Typography>
                     <ToggleButtonGroup
                        value={settings.days_of_week || []}
                        onChange={handleDaysChange}
                        aria-label="дни недели"
                        fullWidth
                    >
                        {days.map(day => <ToggleButton key={day.key} value={day.key} sx={{flexGrow: 1}}>{day.label}</ToggleButton>)}
                    </ToggleButtonGroup>
                    <Stack direction="row" spacing={2}>
                        <TextField
                            label="Начало"
                            type="time"
                            value={settings.start_time || '09:00'}
                            onChange={(e) => onChange('start_time', e.target.value)}
                            fullWidth
                            InputLabelProps={{ shrink: true }}
                        />
                         <TextField
                            label="Конец"
                            type="time"
                            value={settings.end_time || '21:00'}
                            onChange={(e) => onChange('end_time', e.target.value)}
                            fullWidth
                            InputLabelProps={{ shrink: true }}
                        />
                    </Stack>
                </Stack>
            )}
        </Stack>
    );
};


const AutomationSettingsModal = ({ open, onClose, automation }) => {
    const queryClient = useQueryClient();
    const [settings, setSettings] = useState({});
    const userInfo = useUserStore(state => state.userInfo);

    useEffect(() => {
        if (open && automation) {
            const defaults = {
                count: 50,
                filters: { sex: 0, is_online: false, allow_closed_profiles: false, remove_banned: true, last_seen_hours: 0, last_seen_days: 0, min_friends: null, max_friends: null, min_followers: null, max_followers: null },
                message_template_default: "С Днем Рождения, {name}! Желаю всего самого наилучшего, успехов и ярких моментов в жизни.",
                schedule_type: 'always',
                start_time: '09:00',
                end_time: '21:00',
                days_of_week: [0, 1, 2, 3, 4],
            };
            setSettings({ ...defaults, ...(automation.settings || {}) });
        }
    }, [open, automation]);

    const mutation = useMutation({
        mutationFn: updateAutomation,
        onSuccess: (updatedAutomation) => {
            queryClient.setQueryData(['automations'], (oldData) =>
                oldData.map(a => a.automation_type === updatedAutomation.automation_type ? updatedAutomation : a)
            );
            toast.success(`Настройки для "${updatedAutomation.name}" сохранены!`);
            onClose();
        },
        onError: (error) => toast.error(error.response?.data?.detail || 'Ошибка сохранения'),
    });

    const handleSettingsChange = (name, value) => {
        const filterKeys = ['sex', 'is_online', 'allow_closed_profiles', 'remove_banned', 'last_seen_hours', 'last_seen_days', 'min_friends', 'max_friends', 'min_followers', 'max_followers', 'status_keyword'];

        if (filterKeys.includes(name)) {
            setSettings(s => ({ ...s, filters: { ...s.filters, [name]: value } }));
        } else {
            setSettings(s => ({ ...s, [name]: value }));
        }
    };
    
    const handleSave = () => {
        mutation.mutate({
            automationType: automation.automation_type,
            isActive: automation.is_active,
            settings: settings,
        });
    };

    if (!automation) return null;

    const actionConfig = content.actions[automation.automation_type];
    const automationConfig = content.automations.find(a => a.id === automation.automation_type);
    const needsCount = actionConfig && !!actionConfig.modal_count_label;
    const needsFilters = automationConfig && automationConfig.has_filters;
    
    const getLimit = () => {
        if (automation.automation_type.includes('add')) return userInfo?.daily_add_friends_limit || 100;
        if (automation.automation_type.includes('like')) return userInfo?.daily_likes_limit || 1000;
        return 1000;
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
            <DialogTitle sx={{ fontWeight: 600 }}>Настройки: {automation.name}</DialogTitle>
            <DialogContent dividers>
                <Stack spacing={3} py={2}>
                    <Typography variant="body2" color="text.secondary">
                        Здесь вы можете задать параметры для автоматического выполнения задачи. Настройки сохраняются для каждого действия индивидуально.
                    </Typography>
                    
                    {automation.automation_type === 'birthday_congratulation' && (
                        <TextField
                            multiline rows={4} label="Шаблон поздравления" name="message_template_default"
                            value={settings.message_template_default || ''}
                            onChange={(e) => handleSettingsChange(e.target.name, e.target.value)}
                            helperText="Используйте {name} для подстановки имени друга."
                        />
                    )}

                    {automation.automation_type === 'eternal_online' && (
                        <EternalOnlineSettings settings={settings} onChange={handleSettingsChange} />
                    )}

                    {needsCount && (
                        <CountSlider
                            label={actionConfig.modal_count_label}
                            value={settings.count || 20}
                            onChange={(val) => handleSettingsChange('count', val)}
                            max={getLimit()}
                        />
                    )}

                    {needsFilters && <Divider />}

                    {needsFilters && automation.automation_type === 'remove_friends' && (
                        <RemoveFriendsFilters filters={settings.filters || {}} onChange={handleSettingsChange} />
                    )}
                    {needsFilters && !['remove_friends'].includes(automation.automation_type) && (
                        <CommonFiltersSettings
                            filters={settings.filters || {}}
                            onChange={handleSettingsChange}
                            actionKey={automation.automation_type}
                        />
                    )}
                </Stack>
            </DialogContent>
            <DialogActions sx={{p: 2}}>
                <Button onClick={onClose}>Отмена</Button>
                <Button onClick={handleSave} variant="contained" disabled={mutation.isLoading}>
                    {mutation.isLoading ? <CircularProgress size={24} /> : 'Сохранить'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default AutomationSettingsModal;

// --- frontend/src\pages\Dashboard\components\ProfileGrowthWidget.js ---

// frontend/src/pages/Dashboard/components/ProfileGrowthWidget.js
import React, { useState, useMemo } from 'react';
import { Paper, Typography, Box, useTheme, Skeleton, Button, ButtonGroup } from '@mui/material';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { useQuery } from '@tanstack/react-query';
import { fetchProfileGrowth } from 'api.js';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <Paper sx={{ p: 2, background: 'rgba(30, 31, 37, 0.9)', backdropFilter: 'blur(5px)', borderRadius: 2 }}>
                <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>{format(new Date(label), 'd MMMM yyyy', { locale: ru })}</Typography>
                {payload.map(p => (
                    <Typography key={p.name} variant="body2" sx={{ color: p.color }}>
                        {`${p.name}: ${p.value}`}
                    </Typography>
                ))}
            </Paper>
        );
    }
    return null;
};

export default function ProfileGrowthWidget() {
    const [dataType, setDataType] = useState('likes'); // 'likes' or 'friends'
    const theme = useTheme();
    const { data, isLoading } = useQuery({
        queryKey: ['profileGrowth'],
        queryFn: () => fetchProfileGrowth(30),
        staleTime: 1000 * 60 * 60, // 1 hour
    });

    const chartData = useMemo(() => {
        if (!data?.data) return [];
        return data.data.map(item => ({
            date: new Date(item.date).getTime(),
            value: dataType === 'likes' ? item.total_likes_on_content : item.friends_count,
        }));
    }, [data, dataType]);
    
    const metricName = dataType === 'likes' ? 'Сумма лайков' : 'Количество друзей';

    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>Динамика роста профиля</Typography>
                <ButtonGroup size="small">
                    <Button variant={dataType === 'likes' ? 'contained' : 'outlined'} onClick={() => setDataType('likes')}>Лайки</Button>
                    <Button variant={dataType === 'friends' ? 'contained' : 'outlined'} onClick={() => setDataType('friends')}>Друзья</Button>
                </ButtonGroup>
            </Box>
            {isLoading ? (
                <Skeleton variant="rounded" height={250} />
            ) : (
                <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                        <XAxis 
                            dataKey="date" 
                            stroke={theme.palette.text.secondary} 
                            tickFormatter={(timeStr) => format(new Date(timeStr), 'd MMM', { locale: ru })}
                            fontSize="0.8rem"
                        />
                        <YAxis stroke={theme.palette.text.secondary} fontSize="0.8rem" domain={['dataMin - 10', 'dataMax + 10']} />
                        <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                        <Tooltip content={<CustomTooltip />} />
                        <Line type="monotone" dataKey="value" name={metricName} stroke={theme.palette.secondary.main} strokeWidth={3} dot={false} />
                    </LineChart>
                </ResponsiveContainer>
            )}
        </Paper>
    );
}

// --- frontend/src\pages\Dashboard\components\ProfileSummaryWidget.js ---

// frontend/src/pages/Dashboard/components/ProfileSummaryWidget.js (НОВЫЙ ФАЙЛ)
import React from 'react';
import { Grid } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchProfileSummary } from 'api';
import StatCard from 'components/StatCard';

// Иконки
import GroupIcon from '@mui/icons-material/Group';
import RssFeedIcon from '@mui/icons-material/RssFeed';
import PhotoLibraryIcon from '@mui/icons-material/PhotoLibrary';
import ArticleIcon from '@mui/icons-material/Article';

const ProfileSummaryWidget = () => {
    const { data, isLoading } = useQuery({
        queryKey: ['profileSummary'],
        queryFn: fetchProfileSummary,
        staleTime: 1000 * 60 * 60, // 1 час
    });

    const stats = [
        { title: 'Друзья', value: data?.friends, icon: <GroupIcon />, color: 'primary' },
        { title: 'Подписчики', value: data?.followers, icon: <RssFeedIcon />, color: 'secondary' },
        { title: 'Фотографии', value: data?.photos, icon: <PhotoLibraryIcon />, color: 'success' },
        { title: 'Записи на стене', value: data?.wall_posts, icon: <ArticleIcon />, color: 'warning' },
    ];

    return (
        <Grid container spacing={2}>
            {stats.map((stat, index) => (
                <Grid item xs={12} sm={6} key={index}>
                    <StatCard
                        title={stat.title}
                        value={isLoading ? 0 : stat.value}
                        icon={stat.icon}
                        color={stat.color}
                        isLoading={isLoading}
                    />
                </Grid>
            ))}
        </Grid>
    );
};

export default ProfileSummaryWidget;

// --- frontend/src\pages\Dashboard\components\ProxyManagerModal.js ---

// frontend/src/pages/Dashboard/components/ProxyManagerModal.js
import React, { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Box, CircularProgress, Stack, List, ListItem, ListItemText, IconButton, Typography } from '@mui/material';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';
import { apiClient } from 'api';
import DeleteIcon from '@mui/icons-material/Delete';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';

const fetchProxies = async () => (await apiClient.get('/api/v1/proxies')).data;
const addProxy = async (proxyUrl) => (await apiClient.post('/api/v1/proxies', { proxy_url: proxyUrl })).data;
const deleteProxy = async (proxyId) => (await apiClient.delete(`/api/v1/proxies/${proxyId}`));

const ProxyManagerModal = ({ open, onClose }) => {
    const queryClient = useQueryClient();
    const [newProxy, setNewProxy] = useState('');

    const { data: proxies, isLoading } = useQuery({
        queryKey: ['proxies'],
        queryFn: fetchProxies,
        enabled: open, // Загружаем данные только когда модальное окно открыто
    });

    const addMutation = useMutation({
        mutationFn: addProxy,
        onSuccess: () => {
            toast.success("Прокси успешно добавлен и проверен!");
            queryClient.invalidateQueries({ queryKey: ['proxies'] });
            setNewProxy('');
        },
        onError: (err) => toast.error(err.response?.data?.detail || 'Ошибка добавления прокси'),
    });

    const deleteMutation = useMutation({
        mutationFn: deleteProxy,
        onSuccess: () => {
            toast.success("Прокси удален.");
            queryClient.invalidateQueries({ queryKey: ['proxies'] });
        },
        onError: (err) => toast.error(err.response?.data?.detail || 'Ошибка удаления'),
    });

    const handleAddProxy = () => {
        if (!newProxy.trim()) {
            toast.error("Поле не может быть пустым");
            return;
        }
        addMutation.mutate(newProxy.trim());
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle sx={{ fontWeight: 600 }}>Менеджер прокси</DialogTitle>
            <DialogContent dividers>
                <Stack spacing={3}>
                    <Box>
                        <Typography variant="h6" gutterBottom>Добавить новый прокси</Typography>
                        <Stack direction="row" spacing={2}>
                            <TextField
                                fullWidth
                                size="small"
                                label="URL прокси"
                                placeholder="http://user:pass@host:port"
                                value={newProxy}
                                onChange={(e) => setNewProxy(e.target.value)}
                                disabled={addMutation.isLoading}
                            />
                            <Button
                                variant="contained"
                                onClick={handleAddProxy}
                                disabled={addMutation.isLoading}
                                sx={{ flexShrink: 0 }}
                            >
                                {addMutation.isLoading ? <CircularProgress size={24} /> : 'Добавить'}
                            </Button>
                        </Stack>
                    </Box>
                    <Box>
                        <Typography variant="h6" gutterBottom>Сохраненные прокси</Typography>
                        {isLoading && <CircularProgress />}
                        {!isLoading && proxies?.length === 0 && <Typography color="text.secondary">У вас пока нет прокси.</Typography>}
                        <List>
                            {proxies?.map(proxy => (
                                <ListItem
                                    key={proxy.id}
                                    divider
                                    secondaryAction={
                                        <IconButton edge="end" onClick={() => deleteMutation.mutate(proxy.id)} disabled={deleteMutation.isLoading}>
                                            <DeleteIcon />
                                        </IconButton>
                                    }
                                >
                                    {proxy.is_working ? <CheckCircleIcon color="success" sx={{ mr: 1.5 }} /> : <CancelIcon color="error" sx={{ mr: 1.5 }} />}
                                    <ListItemText
                                        primary={proxy.proxy_url}
                                        secondary={proxy.check_status_message}
                                    />
                                </ListItem>
                            ))}
                        </List>
                    </Box>
                </Stack>
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Закрыть</Button>
            </DialogActions>
        </Dialog>
    );
};

export default ProxyManagerModal;

// --- frontend/src\pages\Dashboard\components\StatCard.js ---

// frontend/src/pages/Dashboard/components/StatCard.js
import React from 'react';
import { Paper, Typography, Box, Skeleton, alpha } from '@mui/material';
import { motion } from 'framer-motion';

const StatCard = ({ title, value, icon, isLoading, color = 'primary' }) => {
    return (
        <Paper 
            sx={{ 
                p: 2.5, 
                display: 'flex', 
                alignItems: 'center', 
                gap: 2,
                height: '100%',
                backgroundColor: (theme) => alpha(theme.palette[color].main, 0.1),
                borderColor: (theme) => alpha(theme.palette[color].main, 0.3),
            }}
        >
            <Box sx={{ 
                color: `${color}.main`, 
                fontSize: '2.5rem', 
                display: 'flex',
                p: 1.5,
                borderRadius: '50%',
                backgroundColor: (theme) => alpha(theme.palette[color].main, 0.15)
            }}>
                {icon}
            </Box>
            <Box>
                <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
                    {title}
                </Typography>
                {isLoading ? (
                    <Skeleton variant="text" width={80} height={32} />
                ) : (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} key={value}>
                        <Typography variant="h5" sx={{ fontWeight: 700 }}>
                            {value}
                        </Typography>
                    </motion.div>
                )}
            </Box>
        </Paper>
    );
};

export default StatCard;

// --- frontend/src\pages\Dashboard\components\TaskLogWidget.js ---

// frontend/src/pages/Dashboard/components/TaskLogWidget.js
import React, { useState, useRef, useCallback } from 'react';
import {
    Paper, Typography, Box, CircularProgress, Chip, Collapse, IconButton,
    FormControl, InputLabel, Select, MenuItem, Stack, alpha, Tooltip, Divider
} from '@mui/material';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import ReplayIcon from '@mui/icons-material/Replay';
import CancelIcon from '@mui/icons-material/Cancel';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchTaskHistory, cancelTask, retryTask } from 'api.js';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { AnimatePresence, motion } from 'framer-motion';
import { toast } from 'react-hot-toast';
import TaskParametersViewer from './TaskParametersViewer';

// Иконки для каждого типа задач
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import RecommendIcon from '@mui/icons-material/Recommend';
import HistoryIcon from '@mui/icons-material/History';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';
import FavoriteIcon from '@mui/icons-material/Favorite';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import SendIcon from '@mui/icons-material/Send';
import GroupRemoveIcon from '@mui/icons-material/GroupRemove';

const statusMap = {
    SUCCESS: { label: 'Успешно', color: 'success' },
    FAILURE: { label: 'Ошибка', color: 'error' },
    PENDING: { label: 'В очереди', color: 'info' },
    STARTED: { label: 'Выполняется', color: 'warning' },
    RETRY: { label: 'Повтор', color: 'secondary' },
    CANCELLED: { label: 'Отменена', color: 'default' },
};

const taskIconMap = {
    'Прием заявок': <GroupAddIcon fontSize="small" />,
    'Лайки в ленте': <ThumbUpIcon fontSize="small" />,
    'Добавить друзей': <RecommendIcon fontSize="small" />,
    'Просмотр историй': <HistoryIcon fontSize="small" />,
    'Чистка друзей': <PersonRemoveIcon fontSize="small" />,
    'Лайки друзьям': <FavoriteIcon fontSize="small" />,
    'Массовая рассылка': <SendIcon fontSize="small" />,
    'Отписка от сообществ': <GroupRemoveIcon fontSize="small" />
};

const TaskEntry = React.memo(({ task }) => {
    const [open, setOpen] = useState(false);
    const queryClient = useQueryClient();
    const statusInfo = statusMap[task.status] || { label: task.status, color: 'default' };

    const cancelMutation = useMutation({
        mutationFn: cancelTask,
        onSuccess: () => {
            toast.success("Задача отменена.");
            queryClient.invalidateQueries({ queryKey: ['task_history'] });
        },
        onError: (err) => toast.error(err.response?.data?.detail || "Ошибка отмены"),
    });

    const retryMutation = useMutation({
        mutationFn: retryTask,
        onSuccess: () => {
            toast.success("Задача поставлена на повторное выполнение.");
            queryClient.invalidateQueries({ queryKey: ['task_history'] });
        },
        onError: (err) => toast.error(err.response?.data?.detail || "Ошибка повтора"),
    });
    
    const hasDetails = task.parameters && Object.keys(task.parameters).length > 0;
    const TaskIcon = Object.entries(taskIconMap).find(([key]) => task.task_name.includes(key))?.[1] || <HelpOutlineIcon fontSize="small" />;

    return (
        <motion.div
            layout initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.1 } }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}>
            <Paper variant="outlined" sx={{ mb: 1.5, bgcolor: 'background.default', transition: 'box-shadow 0.2s', '&:hover': { boxShadow: 3, borderColor: 'primary.main' } }}>
                <Box sx={{ p: 2, display: 'flex', alignItems: 'center', gap: 2, cursor: hasDetails ? 'pointer' : 'default' }} onClick={() => hasDetails && setOpen(!open)}>
                    <Box sx={{ width: 40, flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
                        {hasDetails ? <IconButton size="small">{open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}</IconButton> : <Box sx={{width: 28}}/>}
                    </Box>
                    <Typography variant="body2" sx={{ width: 160, flexShrink: 0, color: 'text.secondary' }}>
                        {format(new Date(task.created_at), 'd MMM yyyy, HH:mm', { locale: ru })}
                    </Typography>
                    <Stack direction="row" alignItems="center" spacing={1.5} sx={{ flexGrow: 1, overflow: 'hidden' }}>
                        <Tooltip title={task.task_name} placement="top-start">
                           <Box sx={{ color: 'primary.main', display: 'flex' }}>{TaskIcon}</Box>
                        </Tooltip>
                        <Typography sx={{ fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{task.task_name}</Typography>
                    </Stack>
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <Chip label={statusInfo.label} color={statusInfo.color} size="small" variant="outlined" />
                        {task.status === 'FAILURE' && (
                            <Tooltip title="Повторить задачу">
                                <span>
                                    <IconButton size="small" onClick={(e) => { e.stopPropagation(); retryMutation.mutate(task.id); }} disabled={retryMutation.isLoading}>
                                        <ReplayIcon fontSize="small" color="primary" />
                                    </IconButton>
                                </span>
                            </Tooltip>
                        )}
                        {['PENDING', 'STARTED', 'RETRY'].includes(task.status) && (
                            <Tooltip title="Отменить задачу">
                                 <span>
                                    <IconButton size="small" onClick={(e) => { e.stopPropagation(); cancelMutation.mutate(task.id); }} disabled={cancelMutation.isLoading}>
                                        <CancelIcon fontSize="small" color="error" />
                                    </IconButton>
                                </span>
                            </Tooltip>
                        )}
                    </Stack>
                </Box>
                <Collapse in={open} timeout="auto" unmountOnExit>
                    <Box sx={{ px: 2, pb: 2, pl: '72px' }}>
                        <Box sx={{ bgcolor: (theme) => alpha(theme.palette.divider, 0.3), p: 1.5, borderRadius: 2 }}>
                             <TaskParametersViewer parameters={task.parameters} />
                             {task.result && <Divider sx={{ my: 1 }} />}
                             {task.result && <Typography variant="caption" sx={{ fontFamily: 'monospace' }}>Результат: {task.result}</Typography>}
                        </Box>
                    </Box>
                </Collapse>
            </Paper>
        </motion.div>
    );
});

export default function TaskLogWidget() {
    const [statusFilter, setStatusFilter] = useState('');
    
    const {
        data, error, fetchNextPage, hasNextPage,
        isFetching, isFetchingNextPage, status,
    } = useInfiniteQuery({
        queryKey: ['task_history', statusFilter],
        queryFn: ({ pageParam = 1 }) => fetchTaskHistory({ pageParam }, { status: statusFilter || undefined }),
        getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.page + 1 : undefined),
        initialPageParam: 1,
    });

    const observer = useRef();
    const lastTaskElementRef = useCallback(node => {
        if (isFetchingNextPage) return;
        if (observer.current) observer.current.disconnect();
        observer.current = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && hasNextPage && !isFetching) {
                fetchNextPage();
            }
        });
        if (node) observer.current.observe(node);
    }, [isFetchingNextPage, fetchNextPage, hasNextPage, isFetching]);

    return (
        <Paper sx={{ p: 3, display: 'flex', flexDirection: 'column', height: '100%', minHeight: '500px' }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>Журнал задач</Typography>
                <FormControl sx={{ minWidth: 200 }} size="small">
                    <InputLabel>Статус</InputLabel>
                    <Select value={statusFilter} label="Статус" onChange={(e) => setStatusFilter(e.target.value)}>
                        <MenuItem value=""><em>Все статусы</em></MenuItem>
                        {Object.entries(statusMap).map(([key, value]) => (
                            <MenuItem key={key} value={key}>{value.label}</MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Stack>

            <Box sx={{ flexGrow: 1, overflowY: 'auto', pr: 1, maxHeight: '600px' }}>
                {status === 'pending' && <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>}
                {status === 'error' && <Typography color="error">Ошибка: {error.message}</Typography>}
                
                <AnimatePresence>
                    {data?.pages.map((page, i) => (
                        <React.Fragment key={i}>
                            {page.items.map((task, index) => (
                                <div ref={page.items.length === index + 1 ? lastTaskElementRef : null} key={task.id}>
                                    <TaskEntry task={task} />
                                </div>
                            ))}
                        </React.Fragment>
                    ))}
                </AnimatePresence>

                {isFetchingNextPage && <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}><CircularProgress size={30} /></Box>}
                {!hasNextPage && data?.pages[0]?.items.length > 0 &&
                    <Typography textAlign="center" color="text.secondary" sx={{ mt: 2 }}>Вы загрузили всю историю.</Typography>
                }
                {!data?.pages[0]?.items.length && !isFetching &&
                    <Typography textAlign="center" color="text.secondary" sx={{ mt: 4 }}>Здесь пока нет записей. Запустите задачу, и она появится в истории.</Typography>
                }
            </Box>
        </Paper>
    );
}

// --- frontend/src\pages\Dashboard\components\TaskParametersViewer.js ---

// frontend/src/pages/Dashboard/components/TaskParametersViewer.js
import React from 'react';
import { Box, Typography, List, ListItem, ListItemIcon, ListItemText, Divider } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import FilterListIcon from '@mui/icons-material/FilterList';

const sexMap = { 1: "Женский", 2: "Мужской" };

const ParameterItem = ({ icon, primary, secondary }) => (
    <ListItem sx={{ py: 0.5, px: 1 }}>
        <ListItemIcon sx={{ minWidth: 32, color: 'text.secondary' }}>{icon}</ListItemIcon>
        <ListItemText 
            primary={<Typography variant="body2">{primary}</Typography>} 
            secondary={secondary ? <Typography variant="caption">{secondary}</Typography> : null} 
        />
    </ListItem>
);

const TaskParametersViewer = ({ parameters }) => {
    if (!parameters || Object.keys(parameters).length === 0) {
        return <Typography variant="caption" color="text.secondary">Без дополнительных параметров.</Typography>;
    }

    const { count, filters, message_text, like_config, send_message_on_add } = parameters;
    const hasFilters = filters && Object.values(filters).some(val => val);

    return (
        <Box>
            <List dense>
                {count && <ParameterItem icon={<CheckCircleOutlineIcon fontSize="small"/>} primary={`Количество: ${count}`} />}
                
                {send_message_on_add && <ParameterItem icon={<CheckCircleOutlineIcon fontSize="small"/>} primary="Приветственное сообщение" />}
                
                {like_config?.enabled && <ParameterItem icon={<CheckCircleOutlineIcon fontSize="small"/>} primary="Лайк после заявки" />}

                {message_text && <ParameterItem icon={<CheckCircleOutlineIcon fontSize="small"/>} primary={`Текст: "${message_text}"`} />}

                {hasFilters && (
                    <>
                        <Divider sx={{ my: 1, mx: -2 }} />
                        <Typography variant="subtitle2" sx={{ fontWeight: 600, px: 1, mb: 0.5 }}>Фильтры:</Typography>
                        {filters.is_online && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary="Только онлайн" />}
                        {filters.sex && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Пол: ${sexMap[filters.sex]}`} />}
                        {filters.allow_closed_profiles && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary="Включая закрытые профили" />}
                        {filters.status_keyword && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Статус содержит: "${filters.status_keyword}"`} />}
                        {filters.min_friends && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Друзей: от ${filters.min_friends}`} />}
                        {filters.max_friends && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Друзей: до ${filters.max_friends}`} />}
                        {filters.min_followers && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Подписчиков: от ${filters.min_followers}`} />}
                        {filters.max_followers && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Подписчиков: до ${filters.max_followers}`} />}
                        {filters.last_seen_days && <ParameterItem icon={<FilterListIcon fontSize="small"/>} primary={`Не заходили более: ${filters.last_seen_days} дней`} />}
                    </>
                )}
            </List>
        </Box>
    );
};

export default TaskParametersViewer;

// --- frontend/src\pages\Dashboard\components\UnifiedActionPanel.js ---

// frontend/src/pages/Dashboard/components/UnifiedActionPanel.js
import React from 'react';
import { Paper, Typography, Stack, Switch, Tooltip, Box, CircularProgress, Skeleton, IconButton, alpha } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchAutomations, updateAutomation } from 'api.js';
import { toast } from 'react-hot-toast';
import { content } from 'content/content';
import { motion } from 'framer-motion';

const ActionRow = ({ action, automation, onRun, onSettings, onToggle, isToggling }) => {
    const isAvailable = automation?.is_available ?? true;
    const isActive = automation?.is_active ?? false;
    const isMutatingThisRow = isToggling && onToggle.variables?.automationType === action.id;
    
    const handleToggle = (event) => {
        const newIsActive = event.target.checked;
        // --- ИЗМЕНЕНИЕ: Проверяем доступность функции ПЕРЕД отправкой мутации ---
        if (newIsActive && !isAvailable) {
            toast.error(`Автоматизация недоступна на вашем тарифе.`);
            return;
        }
        onToggle.mutate({ automationType: action.id, isActive: newIsActive, settings: automation?.settings || {} });
    };

    return (
        <motion.div whileHover={{ scale: 1.02 }} transition={{ type: 'spring', stiffness: 400, damping: 10 }}>
            <Paper
                variant="outlined"
                sx={{
                    p: 2, display: 'flex', alignItems: 'center', gap: 2,
                    // --- ИЗМЕНЕНИЕ: Делаем недоступные функции полупрозрачными ---
                    opacity: automation?.is_available ? 1 : 0.6,
                    transition: 'all 0.3s ease',
                    '&:hover': isAvailable ? {
                        boxShadow: 3,
                        borderColor: 'primary.main',
                        bgcolor: (theme) => alpha(theme.palette.primary.main, 0.05),
                    } : {},
                }}
            >
                <Box sx={{ color: 'primary.main', fontSize: '2rem' }}>{action.icon}</Box>
                <Box sx={{ flexGrow: 1 }}>
                     <Typography component="div" variant="body1" sx={{ fontWeight: 600 }}>{action.name}</Typography>
                     <Typography variant="caption" color="text.secondary">{action.description}</Typography>
                </Box>
                <Stack direction="row" spacing={0.5} alignItems="center">
                    {/* --- ИЗМЕНЕНИЕ: Новая логика кнопок --- */}
                    <Tooltip title="Настроить и запустить вручную">
                        <IconButton onClick={() => onRun(action.id, action.name)}><PlayArrowIcon /></IconButton>
                    </Tooltip>
                    <Tooltip title={isAvailable ? "Настроить автоматизацию" : "Недоступно на вашем тарифе"}>
                         <span>
                             <IconButton onClick={() => onSettings(automation)} disabled={!isAvailable}>
                                 <SettingsIcon fontSize="small" />
                             </IconButton>
                         </span>
                    </Tooltip>
                    <Tooltip title={!isAvailable ? "Функция автоматизации недоступна на вашем тарифе" : (isActive ? "Выключить автоматизацию" : "Включить автоматизацию")}>
                        <Box sx={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center', width: 40, height: 24 }}>
                            {isMutatingThisRow && <CircularProgress size={24} sx={{ position: 'absolute' }} />}
                            <Switch
                                checked={isActive}
                                onChange={handleToggle}
                                disabled={!isAvailable || isMutatingThisRow}
                                color="success"
                                sx={{ opacity: isMutatingThisRow ? 0 : 1 }}
                            />
                        </Box>
                    </Tooltip>
                </Stack>
            </Paper>
        </motion.div>
    );
};

export default function UnifiedActionPanel({ onRun, onSettings }) {
    const queryClient = useQueryClient();
    const { data: automations, isLoading } = useQuery({ queryKey: ['automations'], queryFn: fetchAutomations });
    
    const toggleMutation = useMutation({
        mutationFn: updateAutomation,
        onSuccess: (updatedAutomation) => {
            queryClient.setQueryData(['automations'], (oldData) =>
                oldData?.map(a => a.automation_type === updatedAutomation.automation_type ? updatedAutomation : a)
            );
            const statusText = updatedAutomation.is_active ? "активирована" : "остановлена";
            toast.success(`Автоматизация "${updatedAutomation.name}" ${statusText}!`);
        },
        onError: (error) => {
            toast.error(error?.response?.data?.detail || "Не удалось сохранить изменения.");
            queryClient.invalidateQueries({ queryKey: ['automations'] });
        },
    });

    const automationsMap = React.useMemo(() => 
        automations?.reduce((acc, curr) => {
            acc[curr.automation_type] = curr;
            return acc;
        }, {})
    , [automations]);
    
    return (
        <Paper sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>Панель действий</Typography>
            <Stack spacing={2} sx={{ flexGrow: 1, overflowY: 'auto', pr: 1 }}>
                {isLoading ? (
                    Array.from(new Array(5)).map((_, index) => <Skeleton key={index} variant="rounded" height={72} />)
                ) : (
                    content.automations.map(action => (
                         <ActionRow
                            key={action.id}
                            action={action}
                            automation={automationsMap?.[action.id]}
                            onRun={onRun}
                            onSettings={onSettings}
                            onToggle={toggleMutation}
                            isToggling={toggleMutation.isLoading}
                        />
                    ))
                )}
            </Stack>
        </Paper>
    );
}

// --- frontend/src\pages\Dashboard\components\UserProfileCard.js ---

// frontend/src/pages/Dashboard/components/UserProfileCard.js
import React from 'react';
import { Box, Paper, Link, Chip, Stack, Typography, Avatar, Grid, Button, Tooltip, Select, MenuItem, keyframes } from '@mui/material';
import { useUserActions } from 'store/userStore';
import { useFeatureFlag } from 'hooks/useFeatureFlag';
import { useMutation } from '@tanstack/react-query';
import { updateUserDelayProfile } from 'api';
import { toast } from 'react-hot-toast';

import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import SpeedIcon from '@mui/icons-material/Speed';
import ShutterSpeedIcon from '@mui/icons-material/ShutterSpeed';
import SlowMotionVideoIcon from '@mui/icons-material/SlowMotionVideo';

// --- ИЗМЕНЕНИЕ: Анимация для онлайн статуса ---
const pulseAnimation = keyframes`
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(50, 215, 75, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(50, 215, 75, 0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(50, 215, 75, 0); }
`;

// --- ИЗМЕНЕНИЕ: Новый, стильный компонент статуса в стиле Discord ---
const ConnectionStatusIndicator = ({ status }) => {
    
    const statusConfig = {
        'На связи': { label: 'Онлайн', color: 'success.main', animation: `${pulseAnimation} 2s infinite` },
        'Переподключение...': { label: 'Переподключение', color: 'warning.main' },
        'Отключено': { label: 'Отключено', color: 'error.main' },
        'Соединение...': { label: 'Соединение', color: 'info.main' },
    };
    
    const config = statusConfig[status] || { label: 'Неизвестно', color: 'text.secondary' };

    return (
        <Chip 
            label={config.label}
            size="small"
            sx={{
                '& .MuiChip-label': { fontWeight: 600 },
                '& .MuiChip-icon': {
                    color: config.color,
                    animation: config.animation,
                    borderRadius: '50%',
                    width: '10px',
                    height: '10px',
                },
            }}
            icon={<span />}
        />
    );
};


export const UserProfileCard = React.memo(({ userInfo, connectionStatus, onProxyManagerOpen }) => {
    const { isFeatureAvailable } = useFeatureFlag();
    const { setUserInfo } = useUserActions();
    const canUseProxyManager = isFeatureAvailable('proxy_management');
    const canChangeSpeed = isFeatureAvailable('fast_slow_delay_profile');

    const mutation = useMutation({
        mutationFn: updateUserDelayProfile,
        onSuccess: (response) => { setUserInfo(response.data); toast.success(`Скорость работы изменена!`); },
        onError: () => toast.error("Не удалось изменить скорость.")
    });

    const handleSpeedChange = (event) => mutation.mutate({ delay_profile: event.target.value });

    return (
        <Paper sx={{ p: 3, display: 'flex', flexDirection: { xs: 'column', sm: 'row' }, alignItems: 'center', gap: 3, height: '100%' }}>
            <Avatar src={userInfo.photo_200} sx={{ width: 100, height: 100, flexShrink: 0, border: '4px solid', borderColor: 'background.default', boxShadow: 3 }} />
            <Box flexGrow={1} width="100%">
                 <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} sx={{mb: 1.5}}>
                     <Link href={`https://vk.com/id${userInfo.vk_id}`} target="_blank" color="text.primary" sx={{ textDecoration: 'none' }}>
                        <Typography variant="h5" sx={{ fontWeight: 700, '&:hover': { color: 'primary.main' } }}>{userInfo.first_name} {userInfo.last_name}</Typography>
                    </Link>
                    {/* --- ИЗМЕНЕНИЕ: Используем новый компонент статуса --- */}
                    <ConnectionStatusIndicator status={connectionStatus} />
                </Stack>
                <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" sx={{ mb: 2 }}>
                    <Chip icon={<WorkspacePremiumIcon />} label={userInfo.plan} color="primary" variant="filled" size="small"/>
                    {userInfo.plan_expires_at && <Typography variant="caption" color="text.secondary">До {new Date(userInfo.plan_expires_at).toLocaleDateString('ru-RU')}</Typography>}
                </Stack>
                <Grid container spacing={1} alignItems="center">
                    <Grid item xs={12} sm={6} md={4}>
                         <Tooltip title={canUseProxyManager ? "Управление прокси" : "Доступно на PRO-тарифе"}>
                            <span>
                                <Button fullWidth size="small" startIcon={<VpnKeyIcon />} onClick={onProxyManagerOpen} disabled={!canUseProxyManager} variant="outlined" sx={{color: 'text.secondary'}}>Прокси</Button>
                            </span>
                        </Tooltip>
                    </Grid>
                    <Grid item xs={12} sm={6} md={8}>
                        <Tooltip title={!canChangeSpeed ? "Смена скорости доступна на PRO-тарифе" : ""}>
                            <Select
                                fullWidth size="small" value={userInfo.delay_profile} onChange={handleSpeedChange} disabled={mutation.isLoading || !canChangeSpeed}
                                renderValue={(value) => (
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        {value === 'fast' && <ShutterSpeedIcon fontSize="small" />}
                                        {value === 'normal' && <SpeedIcon fontSize="small" />}
                                        {value === 'slow' && <SlowMotionVideoIcon fontSize="small" />}
                                        {value === 'fast' && 'Быстрый'}
                                        {value === 'normal' && 'Стандарт'}
                                        {value === 'slow' && 'Медленный'}
                                    </Box>
                                )}>
                                <MenuItem value="slow"><SlowMotionVideoIcon sx={{mr: 1}}/> Медленный (Макс. безопасность)</MenuItem>
                                <MenuItem value="normal"><SpeedIcon sx={{mr: 1}}/> Стандарт (Баланс)</MenuItem>
                                <MenuItem value="fast"><ShutterSpeedIcon sx={{mr: 1}}/> Быстрый (Макс. скорость)</MenuItem>
                            </Select>
                        </Tooltip>
                    </Grid>
                </Grid>
            </Box>
        </Paper>
    );
});

// --- frontend/src\pages\Home\HomePage.js ---

// frontend/src/pages/Home/HomePage.js
import React from 'react';
import { Box, alpha, Container } from '@mui/material';
import HeroSection from './components/HeroSection';
import FeaturesSection from './components/FeaturesSection';
import AdvantageSection from './components/AdvantageSection';
import StepsSection from './components/StepsSection';
import CtaSection from './components/CtaSection';
import CaseStudiesSection from './components/CaseStudiesSection';
import PrinciplesSection from './components/PrinciplesSection';
import FaqSection from './components/FaqSection';

export const SectionWrapper = ({ children, background = 'transparent', py = { xs: 8, md: 12 } }) => (
    <Box sx={{ py, backgroundColor: background, overflow: 'hidden' }}>
        <Container maxWidth="lg">
            {children}
        </Container>
    </Box>
);

export default function HomePage() {
  return (
    <Box>
      <SectionWrapper py={{ xs: 12, md: 16 }}>
        <HeroSection />
      </SectionWrapper>

      <SectionWrapper background={(theme) => alpha(theme.palette.background.paper, 0.5)}>
        <FeaturesSection />
      </SectionWrapper>
      
      <SectionWrapper>
        <AdvantageSection />
      </SectionWrapper>
      
      <SectionWrapper background={(theme) => alpha(theme.palette.background.paper, 0.5)}>
        <CaseStudiesSection />
      </SectionWrapper>
      
      <SectionWrapper>
        <StepsSection />
      </SectionWrapper>
      
      <SectionWrapper background={(theme) => alpha(theme.palette.background.paper, 0.5)}>
        <PrinciplesSection />
      </SectionWrapper>
      
      <SectionWrapper>
        <FaqSection />
      </SectionWrapper>
      
      <SectionWrapper>
        <CtaSection />
      </SectionWrapper>
    </Box>
  );
}

// --- frontend/src\pages\Home\components\AdvantageSection.js ---

// frontend/src/pages/Home/components/AdvantageSection.js
import React from 'react';
import { Typography, Stack, Paper, alpha, useTheme, Grid } from '@mui/material';
import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SecurityIcon from '@mui/icons-material/Security';
import TimerIcon from '@mui/icons-material/Timer';

const projectionData = [
  { name: 'Старт', 'Охват': 350, 'Подписчики': 1000 },
  { name: 'Неделя 1', 'Охват': 520, 'Подписчики': 1015 },
  { name: 'Неделя 2', 'Охват': 810, 'Подписчики': 1045 },
  { name: 'Неделя 3', 'Охват': 1350, 'Подписчики': 1110 },
  { name: 'Неделя 4', 'Охват': 2280, 'Подписчики': 1250 },
  { name: 'Неделя 5', 'Охват': 3450, 'Подписчики': 1480 },
  { name: 'Неделя 6', 'Охват': 5250, 'Подписчики': 1800 },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <Paper sx={{ p: 2, background: 'rgba(30, 31, 37, 0.9)', backdropFilter: 'blur(5px)', borderRadius: 2 }}>
                <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>{label}</Typography>
                {payload.map(p => (
                    <Typography key={p.name} variant="body2" sx={{ color: p.color }}>
                        {`${p.name}: ${p.value.toLocaleString('ru-RU')}`}
                    </Typography>
                ))}
            </Paper>
        );
    }
    return null;
};


const AdvantageSection = () => {
    const theme = useTheme();

    return (
        <Grid container spacing={6} alignItems="center">
            <Grid item xs={12} md={5}>
                 <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.5 }}>
                    <motion.div variants={fadeInUp}>
                        <Typography variant="h3" component="h2" sx={{ fontWeight: 700, mb: 2 }}>
                           Ваше технологическое преимущество
                        </Typography>
                        <Typography variant="h6" color="text.secondary" sx={{ mb: 4 }}>
                            Мы объединили передовые технологии и глубокое понимание алгоритмов, чтобы вы получали измеримый результат.
                        </Typography>
                    </motion.div>
                    <Stack spacing={3}>
                        <motion.div variants={fadeInUp}>
                            <Stack direction="row" spacing={2}><SecurityIcon color="primary"/><Typography><b>Безопасность — наш приоритет:</b> работа через временный токен VK и поддержка личных прокси для полной анонимности.</Typography></Stack>
                        </motion.div>
                        <motion.div variants={fadeInUp}>
                            <Stack direction="row" spacing={2}><AutoAwesomeIcon color="primary"/><Typography><b>Интеллектуальная имитация:</b> алгоритм Humanizer™ делает автоматизацию неотличимой от ручной работы, предотвращая блокировки.</Typography></Stack>
                        </motion.div>
                         <motion.div variants={fadeInUp}>
                            <Stack direction="row" spacing={2}><TimerIcon color="primary"/><Typography><b>Автоматизация 24/7:</b> настройте сценарии один раз, и Zenith будет работать на вас круглосуточно, даже когда вы оффлайн.</Typography></Stack>
                        </motion.div>
                    </Stack>
                 </motion.div>
            </Grid>
            <Grid item xs={12} md={7}>
                <motion.div initial={{ opacity: 0, scale: 0.9 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true, amount: 0.5 }} transition={{ duration: 0.7 }}>
                     <Paper sx={{ p: {xs: 2, sm: 3}, height: 400, display: 'flex', flexDirection: 'column' }}>
                         <Typography variant="h6" sx={{ fontWeight: 600 }}>Прогнозируемый рост</Typography>
                         <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Пример влияния регулярной активности на видимость профиля.</Typography>
                         <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={projectionData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke={alpha("#A0A3BD", 0.1)} />
                                <XAxis dataKey="name" stroke="#A0A3BD" fontSize="0.8rem" />
                                <YAxis yAxisId="left" stroke={theme.palette.primary.main} fontSize="0.8rem" />
                                <YAxis yAxisId="right" orientation="right" stroke={theme.palette.secondary.main} fontSize="0.8rem" />
                                <Tooltip content={<CustomTooltip />} />
                                <Legend />
                                <Line yAxisId="left" type="monotone" dataKey="Охват" stroke={theme.palette.primary.main} strokeWidth={3} dot={false}/>
                                <Line yAxisId="right" type="monotone" dataKey="Подписчики" stroke={theme.palette.secondary.main} strokeWidth={3} dot={false}/>
                            </LineChart>
                         </ResponsiveContainer>
                     </Paper>
                </motion.div>
            </Grid>
        </Grid>
    );
};

export default AdvantageSection;

// --- frontend/src\pages\Home\components\CaseStudiesSection.js ---

// frontend/src/pages/Home/components/CaseStudiesSection.js
import React from 'react';
import { Typography, Grid, Paper, Stack, Box, Chip, alpha } from '@mui/material';
import { motion } from 'framer-motion';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import AccessAlarmIcon from '@mui/icons-material/AccessAlarm';

const caseStudiesData = [
  {
    icon: <TrendingUpIcon fontSize="large" />,
    chip: "SMM-Агентство",
    title: "Рост охвата клиента на 270%",
    description: "С помощью гибких сценариев и авто-лайков наш клиент, SMM-агентство, добилось трехкратного роста вовлеченности для своего заказчика в сфере ритейла за 2 месяца.",
    color: "primary"
  },
  {
    icon: <GroupAddIcon fontSize="large" />,
    chip: "Малый бизнес",
    title: "+1200 целевых подписчиков",
    description: "Владелец локальной кофейни использовал авто-добавление по рекомендациям с фильтрацией по городу, что привело к значительному увеличению числа реальных посетителей.",
    color: "secondary"
  },
  {
    icon: <AccessAlarmIcon fontSize="large" />,
    chip: "Частный специалист",
    title: "Экономия 8+ часов в неделю",
    description: "Фотограф полностью автоматизировал прием заявок, поздравления и поддержание активности на странице, высвободив целый рабочий день для творчества и съемок.",
    color: "success"
  },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0, scale: 0.95 },
    animate: { y: 0, opacity: 1, scale: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const CaseStudyCard = ({ icon, chip, title, description, color }) => (
    <motion.div variants={fadeInUp} style={{ height: '100%' }}>
        <Paper 
            sx={{ 
                p: 3, 
                height: '100%',
                display: 'flex', 
                flexDirection: 'column',
                borderColor: `${color}.main`,
                background: (theme) => `radial-gradient(circle at 0% 0%, ${alpha(theme.palette[color].main, 0.1)}, ${theme.palette.background.paper} 40%)`
            }}
        >
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box sx={{ color: `${color}.main`, mb: 2 }}>{icon}</Box>
                <Chip label={chip} color={color} variant="outlined" size="small"/>
            </Stack>
            <Typography variant="h5" sx={{ fontWeight: 700, mb: 1.5, flexGrow: 1 }}>{title}</Typography>
            <Typography color="text.secondary">{description}</Typography>
        </Paper>
    </motion.div>
);

const CaseStudiesSection = () => {
    return (
        <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.2 }}>
            <motion.div variants={fadeInUp}>
                <Typography variant="h3" component="h2" textAlign="center" sx={{ mb: 2, fontWeight: 700 }}>
                    Результаты, а не обещания
                </Typography>
                <Typography variant="h6" color="text.secondary" textAlign="center" sx={{ mb: 8, maxWidth: '700px', mx: 'auto' }}>
                    Zenith — это не просто инструмент. Это катализатор роста для реальных людей и бизнесов.
                </Typography>
            </motion.div>
            <Grid container spacing={4} alignItems="stretch">
                {caseStudiesData.map((study, i) => (
                    <Grid item xs={12} md={4} key={i}>
                        <CaseStudyCard {...study} />
                    </Grid>
                ))}
            </Grid>
        </motion.div>
    );
};

export default CaseStudiesSection;

// --- frontend/src\pages\Home\components\CtaSection.js ---

// frontend/src/pages/Home/components/CtaSection.js
import React from 'react';
import { Paper, Typography, Box, Grid, alpha, Stack, Button } from '@mui/material';
import { motion } from 'framer-motion';
import { Link as RouterLink } from 'react-router-dom';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ForumIcon from '@mui/icons-material/Forum';
import GroupAddIcon from '@mui/icons-material/GroupAdd';

const fadeInUp = {
    initial: { opacity: 0, y: 30 },
    animate: { opacity: 1, y: 0, transition: { duration: 0.7, ease: 'easeOut' } },
};

const StatHighlight = ({ icon, value, label, color }) => (
    <motion.div variants={fadeInUp}>
        <Stack direction="row" alignItems="center" spacing={2}>
            <Box sx={{ color: `${color}.main`, fontSize: '3rem' }}>{icon}</Box>
            <Box>
                <Typography variant="h4" sx={{ fontWeight: 700, color: 'text.primary' }}>{value}</Typography>
                <Typography color="text.secondary">{label}</Typography>
            </Box>
        </Stack>
    </motion.div>
);

const CtaSection = () => {

    return (
        <motion.div initial="initial" whileInView="animate" variants={fadeInUp} viewport={{ once: true, amount: 0.5 }}>
            <Paper 
                sx={{ 
                    p: { xs: 4, md: 6 }, 
                    borderRadius: 4, 
                    position: 'relative',
                    overflow: 'hidden',
                    background: (theme) => `radial-gradient(ellipse at 50% 100%, ${alpha(theme.palette.primary.dark, 0.4)} 0%, ${theme.palette.background.default} 70%)`
                }}
            >
                <Grid container spacing={4} alignItems="center">
                    <Grid item xs={12} md={6}>
                        <Typography variant="h3" component="h2" sx={{ fontWeight: 700, color: 'white', mb: 2 }}>
                            Превратите активность в результат
                        </Typography>
                        <Typography variant="h6" sx={{ my: 3, color: 'text.secondary' }}>
                            Регулярные действия не просто увеличивают охваты. Они создают живое сообщество, стимулируя других пользователей к общению, проявлению симпатий и экспоненциальному росту вашей аудитории.
                        </Typography>
                        <Button variant="contained" size="large" component={RouterLink} to="/login">
                            Начать трансформацию
                        </Button>
                    </Grid>
                    <Grid item xs={12} md={6}>
                        <Stack spacing={4}>
                            <StatHighlight icon={<ThumbUpIcon fontSize="inherit"/>} value="+250%" label="Рост вовлеченности (лайки, комментарии)" color="primary" />
                            <StatHighlight icon={<GroupAddIcon fontSize="inherit"/>} value="до 3000" label="Новых друзей и подписчиков за месяц" color="secondary" />
                            <StatHighlight icon={<ForumIcon fontSize="inherit"/>} value="+150%" label="Увеличение входящих сообщений" color="success" />
                        </Stack>
                    </Grid>
                </Grid>
            </Paper>
        </motion.div>
    );
};

export default CtaSection;

// --- frontend/src\pages\Home\components\FaqSection.js ---

// frontend/src/pages/Home/components/FaqSection.js
import React from 'react';
import { Typography, Accordion, AccordionSummary, AccordionDetails, Box, alpha, Icon } from '@mui/material';
import { motion } from 'framer-motion';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SecurityOutlinedIcon from '@mui/icons-material/SecurityOutlined';
import ComputerOutlinedIcon from '@mui/icons-material/ComputerOutlined';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import VpnKeyOutlinedIcon from '@mui/icons-material/VpnKeyOutlined';
import EventBusyOutlinedIcon from '@mui/icons-material/EventBusyOutlined';

const faqData = [
    { icon: <SecurityOutlinedIcon />, q: 'Насколько безопасно использовать Zenith?', a: 'Абсолютно. Мы используем временный ключ доступа (токен) Kate Mobile, который не дает доступа к вашим личным данным, паролю или сообщениям. К тому же, наш алгоритм Humanizer™ имитирует действия реального человека, сводя риски блокировки к минимуму.' },
    { icon: <ComputerOutlinedIcon />, q: 'Нужно ли мне держать компьютер включенным?', a: 'Нет. Все задачи выполняются на наших защищенных облачных серверах. Вы можете настроить автоматизацию или сценарий, закрыть браузер и заниматься своими делами. Zenith будет работать на вас 24/7.' },
    { icon: <AccountTreeOutlinedIcon />, q: 'Что такое "сценарии" и чем они отличаются от автоматизации?', a: 'Автоматизация — это регулярное выполнение одного конкретного действия (например, авто-прием заявок). Сценарии — это мощный конструктор, где вы можете выстроить целую цепочку из разных действий, которые будут выполняться последовательно по заданному вами расписанию.' },
    { icon: <VpnKeyOutlinedIcon />, q: 'Могу ли я использовать свой прокси-сервер?', a: 'Да, на тарифе PRO вы получаете доступ к менеджеру прокси, где можете добавить, проверить и использовать собственные прокси-серверы для максимальной анонимности и обхода ограничений.' },
    { icon: <EventBusyOutlinedIcon />, q: 'Что произойдет после окончания бесплатного периода?', a: 'После 14-дневного базового периода ваш аккаунт будет переведен на ограниченный тариф "Expired". Все ваши настройки сохранятся, и вы сможете в любой момент выбрать платный тариф, чтобы продолжить использовать все возможности платформы.' },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.1 } }
};

const FaqSection = () => {
    return (
        <Box>
            <motion.div initial="initial" whileInView="animate" variants={fadeInUp} viewport={{ once: true, amount: 0.5 }}>
                 <Typography variant="h3" component="h2" textAlign="center" sx={{ mb: 2, fontWeight: 700 }}>
                    Остались вопросы?
                </Typography>
                <Typography variant="h6" color="text.secondary" textAlign="center" sx={{ mb: 8, maxWidth: '700px', mx: 'auto' }}>
                    Мы собрали ответы на самые популярные из них, чтобы вы могли начать работу без сомнений.
                </Typography>
            </motion.div>
            <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.2 }}>
                <Box maxWidth="md" mx="auto">
                    {faqData.map((faq, i) => (
                        <motion.div variants={fadeInUp} key={i}>
                            <Accordion sx={{
                                mb: 1.5,
                                backgroundImage: 'none',
                                bgcolor: 'background.paper',
                                border: '1px solid',
                                borderColor: 'divider',
                                '&:before': { display: 'none' },
                                '&.Mui-expanded': { 
                                    margin: '0 0 12px 0',
                                    borderColor: 'primary.main',
                                    boxShadow: (theme) => `0 8px 24px ${alpha(theme.palette.primary.main, 0.1)}`,
                                },
                            }}>
                                <AccordionSummary 
                                  expandIcon={<ExpandMoreIcon />}
                                  sx={{ minHeight: 72, '& .MuiAccordionSummary-content': { alignItems: 'center', gap: 2 } }}
                                >
                                    <Icon sx={{ color: 'primary.main' }}>{faq.icon}</Icon>
                                    <Typography variant="h6" sx={{fontWeight: 600}}>{faq.q}</Typography>
                                </AccordionSummary>
                                <AccordionDetails sx={{ pt: 0, pb: 2, px: 3 }}>
                                    <Typography color="text.secondary">{faq.a}</Typography>
                                </AccordionDetails>
                            </Accordion>
                        </motion.div>
                    ))}
                </Box>
            </motion.div>
        </Box>
    );
};

export default FaqSection;

// --- frontend/src\pages\Home\components\FeatureHighlightCard.js ---

// frontend/src/pages/Home/components/FeatureHighlightCard.js
import React from 'react';
import { Stack, Box, Typography } from '@mui/material';
import { motion } from 'framer-motion';

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};

const FeatureHighlightCard = ({ icon, title, description }) => {
    return (
        <motion.div variants={fadeInUp} style={{ height: '100%' }}>
            <Stack spacing={2} direction="row" sx={{ p: 2 }}>
                <Box sx={{ fontSize: '2.5rem', color: 'secondary.main', mt: 0.5 }}>
                    {icon}
                </Box>
                <Box>
                    <Typography variant="h6" sx={{fontWeight: 600}}>{title}</Typography>
                    <Typography color="text.secondary">{description}</Typography>
                </Box>
            </Stack>
        </motion.div>
    );
};

export default FeatureHighlightCard;

// --- frontend/src\pages\Home\components\FeaturesSection.js ---

// frontend/src/pages/Home/components/FeaturesSection.js
import React from 'react';
import { Grid, Typography } from '@mui/material';
import { motion } from 'framer-motion';
import FeatureHighlightCard from './FeatureHighlightCard';
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import BarChartOutlinedIcon from '@mui/icons-material/BarChartOutlined';
import VpnKeyOutlinedIcon from '@mui/icons-material/VpnKeyOutlined';
import CloudQueueOutlinedIcon from '@mui/icons-material/CloudQueueOutlined';
import FilterAltOutlinedIcon from '@mui/icons-material/FilterAltOutlined';

const featuresData = [
    { icon: <HubOutlinedIcon />, title: "Продвинутые сценарии", description: "Создавайте сложные цепочки действий, которые будут выполняться по вашему расписанию 24/7." },
    { icon: <PsychologyOutlinedIcon />, title: "Алгоритм Humanizer™", description: "Интеллектуальные задержки между действиями имитируют поведение человека, минимизируя риски." },
    { icon: <BarChartOutlinedIcon />, title: "Live-аналитика", description: "Отслеживайте динамику роста друзей, подписчиков и охватов на наглядных графиках." },
    { icon: <VpnKeyOutlinedIcon />, title: "Поддержка Proxy", description: "Используйте собственные прокси-серверы для максимальной анонимности и безопасности аккаунта." },
    { icon: <CloudQueueOutlinedIcon />, title: "Облачная работа", description: "Все задачи выполняются на наших серверах. Вам не нужно держать компьютер включенным." },
    { icon: <FilterAltOutlinedIcon />, title: "Детальная фильтрация", description: "Таргетируйте аудиторию по полу, онлайну, активности и другим критериям для максимальной эффективности." },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const FeaturesSection = () => {
  return (
      <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.2 }}>
          <motion.div variants={fadeInUp}>
               <Typography variant="h3" component="h2" textAlign="center" sx={{ mb: 8, fontWeight: 700 }}>
                  Все инструменты для эффективного SMM
              </Typography>
          </motion.div>
          <Grid container spacing={5}>
              {featuresData.map((feature, i) => (
                  <Grid item xs={12} md={6} lg={4} key={i}>
                      <FeatureHighlightCard {...feature} />
                  </Grid>
              ))}
          </Grid>
      </motion.div>
  );
};

export default FeaturesSection;

// --- frontend/src\pages\Home\components\HeroSection.js ---

// frontend/src/pages/Home/components/HeroSection.js
import React from 'react';
import { Container, Typography, Button, Stack } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { motion } from 'framer-motion';

const HeroSection = () => {
  return (
    <Container maxWidth="lg" sx={{ textAlign: 'center' }}>
      <motion.div
        initial="hidden"
        animate="visible"
        variants={{
          hidden: { opacity: 0 },
          visible: { opacity: 1, transition: { staggerChildren: 0.2 } },
        }}
      >
        <motion.div variants={{ hidden: { opacity: 0, y: -20 }, visible: { opacity: 1, y: 0, transition: { duration: 0.7 } } }}>
          <Typography 
            variant="h2"
            component="h1" 
            sx={{
              fontWeight: 800,
              maxWidth: '850px',
              mx: 'auto',
              background: (theme) => `linear-gradient(45deg, ${theme.palette.primary.main} 30%, ${theme.palette.secondary.main} 90%)`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            Интеллектуальная платформа для продвижения ВКонтакте
          </Typography>
        </motion.div>
        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0, transition: { duration: 0.7, delay: 0.2 } } }}>
          <Typography variant="h6" color="text.secondary" paragraph sx={{ mt: 3, mb: 4, maxWidth: '750px', mx: 'auto' }}>
            Zenith — это ваш надежный партнер для органического роста, повышения охватов и комплексной автоматизации рутинных SMM-задач. Сосредоточьтесь на контенте, а мы позаботимся о его продвижении.
          </Typography>
        </motion.div>
        <motion.div variants={{ hidden: { scale: 0.8, opacity: 0 }, visible: { scale: 1, opacity: 1, transition: { duration: 0.5, delay: 0.4 } } }}>
          <Stack direction={{xs: 'column', sm: 'row'}} spacing={2} justifyContent="center">
              <Button variant="contained" size="large" component={RouterLink} to="/login" sx={{py: 1.5, px: 5, fontSize: '1.1rem'}}>
                  Начать бесплатно (14 дней)
              </Button>
              {/* <-- ИЗМЕНЕНИЕ: Кнопка теперь ведет на страницу тарифов --> */}
              <Button variant="outlined" size="large" component={RouterLink} to="/billing" sx={{py: 1.5, px: 5, fontSize: '1.1rem'}}>
                  Узнать больше
              </Button>
          </Stack>
        </motion.div>
      </motion.div>
    </Container>
  );
};

export default HeroSection;

// --- frontend/src\pages\Home\components\PrinciplesSection.js ---

// frontend/src/pages/Home/components/PrinciplesSection.js
import React from 'react';
import { Typography, Grid, Stack, Box } from '@mui/material';
import { motion } from 'framer-motion';
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined';
import PriceCheckOutlinedIcon from '@mui/icons-material/PriceCheckOutlined';
import RocketLaunchOutlinedIcon from '@mui/icons-material/RocketLaunchOutlined';
import CodeOutlinedIcon from '@mui/icons-material/CodeOutlined';

const principlesData = [
    { icon: <VerifiedUserOutlinedIcon sx={{ fontSize: 40 }}/>, title: "Безопасность прежде всего", text: "Мы никогда не запрашиваем ваш пароль. Работа через API-токен и умный алгоритм Humanizer™ гарантируют защиту вашего аккаунта." },
    { icon: <RocketLaunchOutlinedIcon sx={{ fontSize: 40 }}/>, title: "Максимальная эффективность", text: "Наши инструменты, от сценариев до фильтров, созданы для достижения измеримых результатов, а не просто для имитации активности." },
    { icon: <PriceCheckOutlinedIcon sx={{ fontSize: 40 }}/>, title: "Честная цена", text: "Мы верим, что мощные SMM-технологии должны быть доступны каждому. Вы получаете максимум функций без скрытых платежей." },
    { icon: <CodeOutlinedIcon sx={{ fontSize: 40 }}/>, title: "Постоянное развитие", text: "Мы регулярно обновляем платформу, добавляя новые возможности и адаптируясь к изменениям алгоритмов ВКонтакте." },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};

const PrinciplesSection = () => {
    return (
        <Box>
            <motion.div initial="initial" whileInView="animate" variants={fadeInUp} viewport={{ once: true, amount: 0.5 }}>
                <Typography variant="h3" component="h2" textAlign="center" sx={{ mb: 8, fontWeight: 700 }}>
                    Наша философия
                </Typography>
            </motion.div>
            <Grid container spacing={5}>
                {principlesData.map((item, i) => (
                    <Grid item xs={12} md={6} key={i}>
                        <motion.div initial="initial" whileInView="animate" variants={fadeInUp} viewport={{ once: true, amount: 0.5 }}>
                            <Stack direction="row" spacing={3}>
                                <Box sx={{ color: 'primary.main', mt: 0.5 }}>{item.icon}</Box>
                                <Box>
                                    <Typography variant="h5" sx={{ fontWeight: 600, mb: 1 }}>{item.title}</Typography>
                                    <Typography color="text.secondary">{item.text}</Typography>
                                </Box>
                            </Stack>
                        </motion.div>
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};

export default PrinciplesSection;

// --- frontend/src\pages\Home\components\StepCard.js ---

// frontend/src/pages/Home/components/StepCard.js
import React from 'react';
import { Paper, Stack, Typography, Box, alpha } from '@mui/material';
import { motion } from 'framer-motion';

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};

const StepCard = ({ num, icon, title, desc }) => {
    return (
        <motion.div variants={fadeInUp} style={{ height: '100%' }} whileHover={{ y: -8, transition: { type: 'spring', stiffness: 300 } }}>
            <Paper 
                variant="outlined"
                sx={{ 
                    p: 4, 
                    textAlign: 'center', 
                    height: '100%', 
                    position: 'relative', 
                    overflow: 'hidden',
                    bgcolor: 'background.paper',
                    transition: 'border-color 0.3s, box-shadow 0.3s',
                    '&:hover': {
                        borderColor: 'primary.main',
                        boxShadow: (theme) => `0 8px 32px ${alpha(theme.palette.primary.main, 0.1)}`
                    }
                }}
            >
                <Typography 
                    variant="h1" 
                    sx={{
                        position: 'absolute',
                        top: 0, // ИСПРАВЛЕНИЕ: Выравнивание
                        right: 16, // ИСПРАВЛЕНИЕ: Выравнивание
                        fontWeight: 800,
                        fontSize: '8rem', // Уменьшен для лучшего вида
                        lineHeight: 1,
                        color: (theme) => alpha(theme.palette.text.primary, 0.03), // Сделан еще прозрачнее
                        zIndex: 0,
                        userSelect: 'none'
                    }}
                >
                    {num}
                </Typography>
                <Stack spacing={2} alignItems="center" sx={{ position: 'relative', zIndex: 1 }}>
                    <Box sx={{ fontSize: '3rem', color: 'primary.main' }}>{icon}</Box>
                    <Typography variant="h5" sx={{ fontWeight: 600 }}>{title}</Typography>
                    <Typography color="text.secondary">{desc}</Typography>
                </Stack>
            </Paper>
        </motion.div>
    );
};

export default StepCard;

// --- frontend/src\pages\Home\components\StepsSection.js ---

// frontend/src/pages/Home/components/StepsSection.js
import React from 'react';
import { Grid, Typography, Container } from '@mui/material';
import { motion } from 'framer-motion';
import StepCard from './StepCard';

// Иконки
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import AnalyticsOutlinedIcon from '@mui/icons-material/AnalyticsOutlined';

const stepsData = [
    { num: "1", icon: <ShieldOutlinedIcon fontSize="inherit" />, title: "Безопасная авторизация", desc: "Получите временный ключ доступа VK. Мы никогда не запрашиваем и не храним ваш логин и пароль." },
    { num: "2", icon: <TuneOutlinedIcon fontSize="inherit" />, title: "Гибкая настройка", desc: "Выберите действие, настройте мощные фильтры или создайте собственный сценарий работы по расписанию." },
    { num: "3", icon: <AnalyticsOutlinedIcon fontSize="inherit" />, title: "Анализ и контроль", desc: "Наблюдайте за выполнением каждой операции в реальном времени и отслеживайте рост вашего аккаунта." },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const StepsSection = () => {
    return (
        <Container maxWidth="lg">
            <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.3 }}>
                <motion.div variants={fadeInUp}>
                    <Typography variant="h3" component="h2" textAlign="center" gutterBottom sx={{ mb: 8, fontWeight: 700 }}>
                        Всего 3 шага к результату
                    </Typography>
                </motion.div>
                <Grid container spacing={4} alignItems="stretch">
                    {stepsData.map((step) => (
                        <Grid item xs={12} md={4} key={step.num}>
                             <StepCard {...step} />
                        </Grid>
                    ))}
                </Grid>
            </motion.div>
        </Container>
    );
};

export default StepsSection;

// --- frontend/src\pages\Login\LoginPage.js ---

// frontend/src/pages/Login/LoginPage.js
import React, { useState } from 'react';
import { Paper, Typography, TextField, Button, CircularProgress, Alert, Box, Tooltip, Container } from '@mui/material';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import { motion } from 'framer-motion';
import { loginWithVkToken } from 'api.js';
import { useUserActions } from 'store/userStore';
import { content } from 'content/content';

const getErrorMessage = (error) => {
    if (typeof error?.response?.data?.detail === 'string') {
        return error.response.data.detail;
    }
    return content.loginPage.errors.default;
};

export default function LoginPage() {
    const { login } = useUserActions();
    const [vkTokenInput, setVkTokenInput] = useState('');
    const [message, setMessage] = useState('');
    const [loading, setLoading] = useState(false);

    const handleTokenLogin = async () => {
        if (!vkTokenInput.trim()) {
            setMessage(content.loginPage.errors.emptyToken);
            return;
        }

        let tokenToUse = vkTokenInput.trim();
        if (tokenToUse.includes('access_token=')) {
            try {
                const params = new URLSearchParams(tokenToUse.split('#')[1]);
                tokenToUse = params.get('access_token');
                if (!tokenToUse) throw new Error();
            } catch {
                setMessage(content.loginPage.errors.invalidUrl);
                return;
            }
        }

        setLoading(true);
        setMessage('');
        try {
          const response = await loginWithVkToken(tokenToUse);
          login(response.data.access_token);
        } catch (error) {
          const errorMessage = getErrorMessage(error);
          setMessage(errorMessage);
        }
        setLoading(false);
    };

    return (
        <Container maxWidth="sm" sx={{ display: 'flex', alignItems: 'center', py: { xs: 4, md: 12 } }}>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} style={{ width: '100%' }}>
                <Paper sx={{ p: {xs: 3, md: 5 }, textAlign: 'center' }}>
                    <Typography component="h1" variant="h4" gutterBottom sx={{ fontWeight: 700 }}>
                        {content.loginPage.title}
                    </Typography>
                    <Box sx={{display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1, mb: 4}}>
                        <Typography variant="body1" color="text.secondary">
                            {content.loginPage.subtitle}
                        </Typography>
                        <Tooltip
                          title={
                              <Box sx={{ textAlign: 'left', p: 1 }}>
                                  <Typography variant="body2" display="block" sx={{ mb: 1.5 }} dangerouslySetInnerHTML={{ __html: content.loginPage.tooltip.step1 }} />
                                  <Typography variant="body2" display="block" sx={{ mb: 1.5 }}>{content.loginPage.tooltip.step2}</Typography>
                                  <Typography variant="body2" display="block">{content.loginPage.tooltip.step3}</Typography>
                              </Box>
                          }
                          placement="top"
                          arrow
                        >
                            <HelpOutlineIcon fontSize="small" color="secondary" sx={{ cursor: 'help' }}/>
                        </Tooltip>
                    </Box>
                    <TextField
                        fullWidth
                        label={content.loginPage.textFieldLabel}
                        variant="outlined"
                        value={vkTokenInput}
                        onChange={(e) => setVkTokenInput(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && !loading && handleTokenLogin()}
                        sx={{ mb: 2 }}
                    />
                    <Button
                        variant="contained"
                        size="large"
                        fullWidth
                        onClick={handleTokenLogin}
                        disabled={loading}
                        sx={{ py: 1.5, fontSize: '1.1rem' }}
                    >
                        {loading ? <CircularProgress size={26} color="inherit" /> : content.loginPage.buttonText}
                    </Button>
                    {message && <Alert severity={'error'} sx={{ mt: 3, textAlign: 'left', borderRadius: 2 }}>{message}</Alert>}
                </Paper>
            </motion.div>
        </Container>
    );
}

// --- frontend/src\pages\Scenarios\ScenarioEditorModal.js ---

// frontend/src/pages/Scenarios/ScenarioEditorModal.js
import React, { useState, useEffect, useRef } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, TextField, Stack, CircularProgress } from '@mui/material';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { createScenario, updateScenario } from 'api';
import { toast } from 'react-hot-toast';
import AddIcon from '@mui/icons-material/Add';
import { CronBuilder } from './components/CronBuilder';
import { ScenarioStepList } from './components/ScenarioStepList';

const ScenarioEditorModal = ({ open, onClose, scenario }) => {
    const queryClient = useQueryClient();
    const [name, setName] = useState('');
    const [schedule, setSchedule] = useState('0 9 * * 1,2,3,4,5');
    const [steps, setSteps] = useState([]);
    const localIdCounter = useRef(0);

    useEffect(() => {
        if (open) {
            localIdCounter.current = 0; 
            if (scenario) {
                setName(scenario.name);
                setSchedule(scenario.schedule);
                setSteps(scenario.steps.map(s => ({ ...s, localId: localIdCounter.current++ })));
            } else {
                setName('');
                setSchedule('0 9 * * 1,2,3,4,5');
                setSteps([{ localId: localIdCounter.current++, action_type: 'like_feed', settings: { count: 50, filters: {} } }]);
            }
        }
    }, [scenario, open]);

    const mutation = useMutation({
        mutationFn: scenario ? updateScenario : createScenario,
        onSuccess: () => {
            toast.success(`Сценарий успешно ${scenario ? 'обновлен' : 'создан'}!`);
            queryClient.invalidateQueries({ queryKey: ['scenarios'] });
            onClose();
        },
        onError: (err) => toast.error(err.response?.data?.detail || 'Ошибка сохранения'),
    });
    
    const handleAddStep = () => setSteps([...steps, { localId: localIdCounter.current++, action_type: 'like_feed', settings: { count: 50, filters: {} } }]);
    const handleRemoveStep = (localId) => setSteps(steps.filter(s => s.localId !== localId));
    const handleStepChange = (localId, field, value) => setSteps(steps.map(s => s.localId === localId ? { ...s, [field]: value } : s));
    
    // --- ИЗМЕНЕНИЕ: Новая функция для обновления настроек разбиения ---
    const handleBatchChange = (localId, newBatchSettings) => {
        setSteps(steps.map(s => 
            s.localId === localId 
                ? { ...s, batch_settings: { ...(s.batch_settings || {}), ...newBatchSettings } } 
                : s
        ));
    };
    
    const handleSave = () => {
        if (!name.trim()) {
            toast.error("Название сценария не может быть пустым.");
            return;
        }
         if (steps.length === 0) {
            toast.error("Добавьте хотя бы один шаг в сценарий.");
            return;
        }
        const payload = {
            name, schedule,
            is_active: scenario?.is_active ?? false,
            steps: steps.map((step, index) => ({
                step_order: index + 1, action_type: step.action_type, settings: step.settings,
            })),
        };
        if (scenario) payload.id = scenario.id;
        mutation.mutate(payload);
    };

    return (
        <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
            <DialogTitle sx={{ fontWeight: 600 }}>{scenario ? 'Редактировать сценарий' : 'Новый сценарий'}</DialogTitle>
            <DialogContent dividers>
                <Stack spacing={3} py={2}>
                    <TextField label="Название сценария" value={name} onChange={(e) => setName(e.target.value)} />
                    <CronBuilder schedule={schedule} setSchedule={setSchedule} />
                    <ScenarioStepList 
                        steps={steps}
                        setSteps={setSteps}
                        onStepChange={handleStepChange}
                        onStepRemove={handleRemoveStep}
                        onBatchChange={handleBatchChange}
                    />
                    <Button startIcon={<AddIcon />} onClick={handleAddStep} sx={{ alignSelf: 'flex-start' }}>Добавить шаг</Button>
                </Stack>
            </DialogContent>
            <DialogActions sx={{ p: 2 }}>
                <Button onClick={onClose}>Отмена</Button>
                <Button onClick={handleSave} variant="contained" disabled={mutation.isLoading}>
                    {mutation.isLoading ? <CircularProgress size={24} /> : 'Сохранить'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

export default ScenarioEditorModal;

// --- frontend/src\pages\Scenarios\ScenarioPage.js ---

// frontend/src/pages/Scenarios/ScenarioPage.js
import React, { useState } from 'react';
import {
    Container, Typography, Box, Button, CircularProgress,
    Paper, Stack, IconButton, Chip, Tooltip, Switch, alpha
} from '@mui/material';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import PauseCircleOutlineIcon from '@mui/icons-material/PauseCircleOutline';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchScenarios, deleteScenario, updateScenario } from 'api';
import { toast } from 'react-hot-toast';
import cronstrue from 'cronstrue/i18n';
import ScenarioEditorModal from './ScenarioEditorModal';
import { content } from 'content/content';

const ScenarioCard = ({ scenario, onEdit, onDelete, onToggle }) => {
    const toggleMutation = useMutation({
        mutationFn: updateScenario,
        onSuccess: onToggle.onSuccess,
        onError: onToggle.onError,
    });

    const handleToggle = (event) => {
        const isActive = event.target.checked;
        toggleMutation.mutate({ ...scenario, is_active: isActive });
    };

    const isMutating = toggleMutation.isLoading;

    return (
        <Paper sx={{ p: 2.5, display: 'flex', alignItems: 'center', gap: 2, transition: 'box-shadow 0.2s', '&:hover': { boxShadow: 3 } }}>
            <Box sx={{ flexGrow: 1 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>{scenario.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                    {cronstrue.toString(scenario.schedule, { locale: "ru" })}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 1.5, flexWrap: 'wrap', gap: 1 }}>
                    {scenario.steps.slice(0, 5).map(step => (
                        <Chip key={step.id} label={content.actions[step.action_type]?.title || step.action_type} size="small" variant="outlined" />
                    ))}
                    {scenario.steps.length > 5 && <Chip label={`+${scenario.steps.length - 5}`} size="small" />}
                </Stack>
            </Box>
            <Stack direction="row" alignItems="center" spacing={0.5}>
                <Tooltip title={scenario.is_active ? "Приостановить" : "Запустить"}>
                    <span>
                        <Switch
                            checked={scenario.is_active} onChange={handleToggle} disabled={isMutating}
                            icon={<PlayCircleOutlineIcon />} checkedIcon={<PauseCircleOutlineIcon />} color="success"
                        />
                    </span>
                </Tooltip>
                <IconButton onClick={() => onEdit(scenario)} disabled={isMutating}><EditIcon /></IconButton>
                <IconButton onClick={() => onDelete(scenario.id)} disabled={isMutating}><DeleteIcon sx={{color: 'error.light'}} /></IconButton>
            </Stack>
        </Paper>
    );
};

export default function ScenariosPage() {
    const queryClient = useQueryClient();
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingScenario, setEditingScenario] = useState(null);

    const { data: scenarios, isLoading } = useQuery({ queryKey: ['scenarios'], queryFn: fetchScenarios });

    const deleteMutation = useMutation({
        mutationFn: deleteScenario,
        onSuccess: () => {
            toast.success("Сценарий удален.");
            queryClient.invalidateQueries({ queryKey: ['scenarios'] });
        },
        onError: (error) => toast.error(error.message || "Ошибка удаления"),
    });
    
    const onToggleSuccess = () => {
        queryClient.invalidateQueries({ queryKey: ['scenarios'] });
        toast.success("Статус сценария обновлен.");
    };

    const handleOpenModal = (scenario = null) => {
        setEditingScenario(scenario);
        setIsModalOpen(true);
    };

    const handleCloseModal = () => {
        setEditingScenario(null);
        setIsModalOpen(false);
    };

    return (
        <>
            <Container maxWidth="md" sx={{ py: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                    <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
                        Мои Сценарии
                    </Typography>
                    <Button
                        variant="contained" startIcon={<AddCircleOutlineIcon />}
                        onClick={() => handleOpenModal()}>
                        Создать сценарий
                    </Button>
                </Box>

                {isLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
                ) : (
                    <Stack spacing={2}>
                        {/* --- ИЗМЕНЕНИЕ: Добавлен блок "empty state" --- */}
                        {scenarios?.length === 0 ? (
                             <Paper sx={{ p: 5, textAlign: 'center', backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.05), borderStyle: 'dashed' }}>
                                <Typography variant="h6" gutterBottom>У вас пока нет ни одного сценария</Typography>
                                <Typography color="text.secondary">Сценарии позволяют автоматически выполнять цепочки действий по заданному расписанию. Нажмите "Создать", чтобы добавить первый.</Typography>
                            </Paper>
                        ) : (
                            scenarios?.map(scenario => (
                                <ScenarioCard
                                    key={scenario.id} scenario={scenario}
                                    onEdit={handleOpenModal} onDelete={deleteMutation.mutate}
                                    onToggle={{ onSuccess: onToggleSuccess, onError: (error) => toast.error(error.message) }}
                                />
                            ))
                        )}
                    </Stack>
                )}
            </Container>
            <ScenarioEditorModal
                open={isModalOpen} onClose={handleCloseModal}
                scenario={editingScenario}
            />
        </>
    );
}

// --- frontend/src\pages\Scenarios\components\constants.js ---

// frontend/src/pages/Scenarios/components/constants.js
export const actionOptions = [
    { key: 'like_feed', title: 'Лайки в ленте', countLabel: 'Количество лайков' },
    { key: 'add_recommended', title: 'Добавить из рекомендаций', countLabel: 'Количество заявок' },
    { key: 'accept_friends', title: 'Прием заявок' },
    { key: 'remove_friends', title: 'Чистка друзей', countLabel: 'Максимум удалений' },
    { key: 'like_friends_feed', title: 'Лайки друзьям', countLabel: 'Количество лайков' },
    { key: 'view_stories', title: 'Просмотр историй' },
];

// --- frontend/src\pages\Scenarios\components\CronBuilder.js ---

// frontend/src/pages/Scenarios/components/CronBuilder.js
import React, { useState, useEffect } from 'react';
import { TextField, Paper, Typography, Grid, ToggleButtonGroup, ToggleButton } from '@mui/material';
import cronstrue from 'cronstrue/i18n';

export const CronBuilder = ({ schedule, setSchedule }) => {
    const parseCron = (cron) => {
        try {
            const [minute, hour, , , dayOfWeek] = cron.split(' ');
            return { minute, hour, dayOfWeek };
        } catch { return { minute: '0', hour: '9', dayOfWeek: '1,2,3,4,5' }; }
    };
    
    const [cronParts, setCronParts] = useState(parseCron(schedule));

    useEffect(() => {
        const { minute, hour, dayOfWeek } = cronParts;
        setSchedule(`${minute} ${hour} * * ${dayOfWeek}`);
    }, [cronParts, setSchedule]);

    const handleTimeChange = (e) => {
        const [hour, minute] = e.target.value.split(':');
        setCronParts(p => ({ ...p, hour: hour || '0', minute: minute || '0' }));
    }

    const handleDaysChange = (event, newDays) => {
        if (newDays.length) {
            setCronParts(p => ({ ...p, dayOfWeek: newDays.join(',') }));
        }
    };
    
    const weekDays = [
        { key: '1', label: 'Пн' }, { key: '2', label: 'Вт' }, { key: '3', label: 'Ср' },
        { key: '4', label: 'Чт' }, { key: '5', label: 'Пт' }, { key: '6', label: 'Сб' }, { key: '0', label: 'Вс' },
    ];
    
    return (
        <Paper variant="outlined" sx={{ p: 2.5, bgcolor: 'transparent' }}>
            <Typography variant="h6" sx={{ mb: 2 }}>Расписание запуска</Typography>
            <Grid container spacing={2} alignItems="center">
                <Grid item xs={12} sm={4}>
                    <TextField
                        label="Время запуска (МСК)" type="time"
                        value={`${(cronParts.hour || '09').padStart(2, '0')}:${(cronParts.minute || '00').padStart(2, '0')}`}
                        onChange={handleTimeChange} fullWidth InputLabelProps={{ shrink: true }}
                    />
                </Grid>
                <Grid item xs={12} sm={8}>
                     <ToggleButtonGroup value={cronParts.dayOfWeek.split(',')} onChange={handleDaysChange} aria-label="дни недели" fullWidth>
                        {weekDays.map(day => <ToggleButton key={day.key} value={day.key} sx={{flexGrow: 1}}>{day.label}</ToggleButton>)}
                    </ToggleButtonGroup>
                </Grid>
                 <Grid item xs={12}>
                    <Typography variant="body2" color="text.secondary">
                        {cronstrue.toString(schedule, { locale: "ru" })}
                    </Typography>
                </Grid>
            </Grid>
        </Paper>
    );
};

// --- frontend/src\pages\Scenarios\components\ScenarioStepList.js ---

// frontend/src/pages/Scenarios/components/ScenarioStepList.js
import React from 'react';
import { DragDropContext, Droppable, Draggable } from '@hello-pangea/dnd';
import { Paper, Stack, Box, Chip, FormControl, Select, MenuItem, IconButton, Typography } from '@mui/material';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import DeleteIcon from '@mui/icons-material/Delete';
import { actionOptions } from './constants';
import { StepSettings } from './ScenarioStepSettings'; // <-- Корректный импорт настроек

// --- ИСПРАВЛЕНИЕ: Этот компонент был случайно удален и заменен другим. Теперь он восстановлен. ---
const ScenarioStep = ({ step, index, onRemove, onChange, onBatchChange }) => (
    <Paper sx={{ p: 2, mb: 2, '&:hover': { boxShadow: 3 } }}>
        <Stack direction="row" spacing={2} alignItems="center">
            <Box sx={{ cursor: 'grab' }}><DragIndicatorIcon color="disabled" /></Box>
            <Chip label={`Шаг ${index + 1}`} />
            <FormControl fullWidth size="small">
                <Select value={step.action_type} onChange={(e) => onChange(step.localId, 'action_type', e.target.value)}>
                    {actionOptions.map(opt => <MenuItem key={opt.key} value={opt.key}>{opt.title}</MenuItem>)}
                </Select>
            </FormControl>
            <IconButton onClick={() => onRemove(step.localId)}><DeleteIcon color="error" /></IconButton>
        </Stack>
        <StepSettings 
            step={step} 
            onSettingsChange={(newSettings) => onChange(step.localId, 'settings', newSettings)} 
            onBatchChange={onBatchChange}
        />
    </Paper>
);

// --- ИСПРАВЛЕНИЕ: Экспорт компонента ScenarioStepList восстановлен. ---
export const ScenarioStepList = ({ steps, setSteps, onStepChange, onStepRemove, onBatchChange }) => {
    const onDragEnd = (result) => {
        if (!result.destination) return;
        const items = Array.from(steps);
        const [reorderedItem] = items.splice(result.source.index, 1);
        items.splice(result.destination.index, 0, reorderedItem);
        setSteps(items);
    };

    return (
        <DragDropContext onDragEnd={onDragEnd}>
            <Typography variant="h6">Последовательность действий</Typography>
            <Droppable droppableId="steps">
                {(provided) => (
                    <Box {...provided.droppableProps} ref={provided.innerRef} sx={{mt: 2}}>
                        {steps.map((step, index) => (
                            <Draggable key={step.localId} draggableId={String(step.localId)} index={index}>
                                {(provided) => (
                                    <div ref={provided.innerRef} {...provided.draggableProps} {...provided.dragHandleProps}>
                                        <ScenarioStep 
                                            step={step} 
                                            index={index}
                                            onRemove={onStepRemove}
                                            onChange={onStepChange}
                                            onBatchChange={onBatchChange}
                                        />
                                    </div>
                                )}
                            </Draggable>
                        ))}
                        {provided.placeholder}
                    </Box>
                )}
            </Droppable>
        </DragDropContext>
    );
};

// --- frontend/src\pages\Scenarios\components\ScenarioStepSettings.js ---

// frontend/src/pages/Scenarios/components/ScenarioStepSettings.js
import React from 'react';
import { Stack, Typography, FormControl, Select, MenuItem, InputLabel } from '@mui/material';
import ActionModalFilters from 'pages/Dashboard/components/ActionModalFilters';
import { content } from 'content/content';
import CountSlider from 'components/CountSlider';
import { useUserStore } from 'store/userStore';

// --- ИСПРАВЛЕНИЕ: Этот код был по ошибке перемещен в другой файл. Теперь он на своем месте. ---
export const StepSettings = ({ step, onSettingsChange, onBatchChange }) => {
    const userInfo = useUserStore(state => state.userInfo);

    const handleFieldChange = (name, value) => {
        const newSettings = { ...step.settings, [name]: value };
        onSettingsChange(newSettings);
    };

    const handleFilterChange = (name, value) => {
        const filterName = name.replace('filters.', '');
        const newFilters = { ...step.settings.filters, [filterName]: value };
        onSettingsChange({ ...step.settings, filters: newFilters });
    };

    const actionConfig = content.actions[step.action_type];
    // --- ИСПРАВЛЕНИЕ: Правильный поиск конфига автоматизации в массиве ---
    const automationConfig = content.automations.find(a => a.id === step.action_type);

    if (!actionConfig || !automationConfig) return null;

    const hasSettings = !['view_stories', 'eternal_online'].includes(step.action_type);

    if (!hasSettings) {
        return <Typography variant="body2" color="text.secondary" sx={{ mt: 2, pl: 1 }}>Для этого действия нет дополнительных настроек.</Typography>;
    }
    
    const getLimit = () => {
        if (step.action_type.includes('add')) return userInfo?.daily_add_friends_limit || 100;
        if (step.action_type.includes('like')) return userInfo?.daily_likes_limit || 1000;
        return 1000;
    };
    
    const canBeBatched = ['add_recommended', 'like_feed', 'like_friends_feed', 'remove_friends'].includes(step.action_type);

    return (
        <Stack spacing={3} sx={{ mt: 2, p: 2, borderTop: '1px solid', borderColor: 'divider' }}>
            {actionConfig.modal_count_label && (
                <CountSlider
                    label={actionConfig.modal_count_label}
                    value={step.settings.count || 20}
                    onChange={(val) => handleFieldChange('count', val)}
                    max={getLimit()}
                />
            )}
            
            {automationConfig.has_filters && (
                 <ActionModalFilters 
                    filters={step.settings.filters || {}} 
                    onChange={handleFilterChange} 
                    actionKey={step.action_type} 
                />
            )}

            {canBeBatched && (
                <FormControl fullWidth size="small">
                    <InputLabel>Разбить выполнение</InputLabel>
                    <Select
                        value={step.batch_settings?.parts || 1}
                        label="Разбить выполнение"
                        onChange={(e) => onBatchChange(step.localId, { parts: e.target.value })}
                    >
                        <MenuItem value={1}>Не разбивать (выполнить за раз)</MenuItem>
                        <MenuItem value={2}>На 2 части</MenuItem>
                        <MenuItem value={3}>На 3 части</MenuItem>
                        <MenuItem value={4}>На 4 части</MenuItem>
                    </Select>
                </FormControl>
            )}
        </Stack>
    );
};

// --- frontend/src\store\authSlice.js ---

// frontend/src/store/authSlice.js
import { disconnectWebSocket } from '../websocket';

export const createAuthSlice = (set, get) => ({
  jwtToken: localStorage.getItem('jwtToken') || null,
  isLoading: true,

  actions: {
    login: (token) => {
      localStorage.setItem('jwtToken', token);
      set({ jwtToken: token });
    },
    logout: () => {
      localStorage.removeItem('jwtToken');
      disconnectWebSocket();
      get().actions.resetUserSlice(); 
      set({ jwtToken: null, isLoading: false });
    },
    finishInitialLoad: () => {
      set({ isLoading: false });
    },
  }
});

// --- frontend/src\store\userSlice.js ---

// frontend/src/store/userSlice.js
import { fetchUserInfo, fetchUserLimits } from 'api';

const initialState = {
    userInfo: null,
    availableFeatures: [], 
    dailyLimits: {
        likes_limit: 0,
        likes_today: 0,
        friends_add_limit: 0,
        friends_add_today: 0,
    }
};

export const createUserSlice = (set, get) => ({
    ...initialState,

    actions: {
        loadUser: async () => {
            if (!get().jwtToken) {
                return get().actions.finishInitialLoad();
            }
            
            try {
                const [userResponse, limitsResponse] = await Promise.all([
                    fetchUserInfo(),
                    fetchUserLimits()
                ]);

                set({
                    userInfo: userResponse.data,
                    availableFeatures: userResponse.data.available_features || [],
                    dailyLimits: limitsResponse.data,
                });
            } catch (error) {
                console.error("Failed to load user data, logging out.", error);
                get().actions.logout(); 
            } finally {
                get().actions.finishInitialLoad();
            }
        },
        
        setUserInfo: (newUserInfo) => {
            set(state => ({
                userInfo: { ...state.userInfo, ...newUserInfo }
            }));
        },

        setDailyLimits: (newLimits) => {
             set(state => ({
                dailyLimits: { ...state.dailyLimits, ...newLimits }
            }));
        },
        
        resetUserSlice: () => set(initialState),
    }
});

// --- frontend/src\store\userStore.js ---

// frontend/src/store/userStore.js
import { create } from 'zustand';
import { createAuthSlice } from './authSlice';
import { createUserSlice } from './userSlice';
import { connectWebSocket, disconnectWebSocket } from '../websocket';

const createWebSocketSlice = (set) => ({
    connectionStatus: 'Соединение...',
    actions: {
        setConnectionStatus: (status) => set({ connectionStatus: status }),
    }
});

export const useUserStore = create((set, get) => {
    const authSlice = createAuthSlice(set, get);
    const userSlice = createUserSlice(set, get);
    const webSocketSlice = createWebSocketSlice(set, get);

    const combinedState = {
        ...authSlice,
        ...userSlice,
        ...webSocketSlice,
        actions: {
            ...authSlice.actions,
            ...userSlice.actions,
            ...webSocketSlice.actions,
        },
    };
    
    delete combinedState.actions.actions;

    return combinedState;
});

export const useUserActions = () => useUserStore(state => state.actions);

useUserStore.subscribe(
    (state, prevState) => {
        if (state.jwtToken && !prevState.jwtToken) {
            connectWebSocket(state.jwtToken);
        } else if (!state.jwtToken && prevState.jwtToken) {
            disconnectWebSocket();
        }
    }
);

const initialToken = useUserStore.getState().jwtToken;
if (initialToken) {
    connectWebSocket(initialToken);
}