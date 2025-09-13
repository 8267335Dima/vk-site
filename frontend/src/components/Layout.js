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