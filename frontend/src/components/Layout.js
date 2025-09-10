// frontend/src/components/Layout.js
import React from 'react';
import {
    Toolbar, Typography, Button, Container, Box, Stack,
    useTheme, useMediaQuery, IconButton, Drawer, List, ListItem, ListItemButton
} from '@mui/material';
import { Link as RouterLink, useLocation, Outlet } from 'react-router-dom';
import { useUserStore } from 'store/userStore';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import MenuIcon from '@mui/icons-material/Menu';
import { layoutContent } from 'content/layoutContent';
import NotificationsBell from './NotificationsBell';

const NavButton = ({ to, children }) => {
    const location = useLocation();
    const isActive = location.pathname === to;
    return (
        <Button
            component={RouterLink}
            to={to}
            sx={{
                fontWeight: 600,
                color: isActive ? 'primary.main' : 'text.primary',
                bgcolor: 'transparent',
                transition: 'all 0.2s ease-in-out',
                '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)', color: 'primary.light' }
            }}
        >
            {children}
        </Button>
    );
};

const MobileDrawer = ({ navItems, open, onClose, onLogout }) => (
    <Drawer anchor="right" open={open} onClose={onClose}>
        <Box sx={{ width: 250, p: 2, height: '100%', bgcolor: 'background.default' }} role="presentation">
            <List>
                {navItems.map((item) => (
                    <ListItem key={item.label} disablePadding>
                        <ListItemButton component={RouterLink} to={item.to} onClick={onClose}>
                             <Typography>{item.label}</Typography>
                        </ListItemButton>
                    </ListItem>
                ))}
                 <ListItem disablePadding sx={{ mt: 2 }}>
                    <Button onClick={onLogout} fullWidth variant="outlined" color="error">{layoutContent.nav.logout}</Button>
                </ListItem>
            </List>
        </Box>
    </Drawer>
);


export default function Layout({ children }) {
    const jwtToken = useUserStore((state) => state.jwtToken);
    const logout = useUserStore((state) => state.logout);
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));
    const [drawerOpen, setDrawerOpen] = React.useState(false);

    const navItems = [
        { label: layoutContent.nav.dashboard, to: "/dashboard" },
        { label: layoutContent.nav.scenarios, to: "/scenarios" },
        { label: layoutContent.nav.history, to: "/history" },
        { label: layoutContent.nav.billing, to: "/billing" },
    ];
    
    // --- ИЗМЕНЕНИЕ: Теперь Outlet рендерит дочерние роуты ---
    const pageContent = children || <Outlet />;

    return (
        <>
            <Box component="header" sx={{ position: 'sticky', top: 0, width: '100%', zIndex: 1100, }}>
                <Container maxWidth="xl">
                    <Toolbar sx={{ py: 1 }}>
                        <Stack direction="row" alignItems="center" spacing={1.5} component={RouterLink} to="/" sx={{textDecoration: 'none'}}>
                           <TrackChangesIcon color="primary" sx={{ fontSize: '2.2rem' }} />
                           <Typography variant="h5" sx={{ color: 'text.primary', fontWeight: 700, display: { xs: 'none', sm: 'block' } }}>
                                {layoutContent.appName}
                           </Typography>
                        </Stack>

                        <Box sx={{ flexGrow: 1 }} />

                        {isMobile ? (
                             <>
                                {jwtToken && (
                                    <>
                                        <NotificationsBell />
                                        <IconButton onClick={() => setDrawerOpen(true)}><MenuIcon /></IconButton>
                                    </>
                                )}
                                {!jwtToken && <Button component={RouterLink} to="/login" variant="contained">{layoutContent.nav.login}</Button>}
                             </>
                        ) : (
                            <Stack direction="row" spacing={1} alignItems="center">
                                {jwtToken && navItems.map(item => <NavButton key={item.to} to={item.to}>{item.label}</NavButton>)}
                                {jwtToken ? (
                                    <>
                                        <NotificationsBell />
                                        <Button onClick={logout} color="primary" variant="text">{layoutContent.nav.logout}</Button>
                                    </>
                                ) : (
                                    <Button component={RouterLink} to="/login" variant="contained" disableElevation>
                                        {layoutContent.nav.login}
                                    </Button>
                                )}
                            </Stack>
                        )}
                    </Toolbar>
                </Container>
                {isMobile && jwtToken && <MobileDrawer navItems={navItems} open={drawerOpen} onClose={() => setDrawerOpen(false)} onLogout={logout} />}
            </Box>

            <Box component="main">
                 {/* --- ИЗМЕНЕНИЕ: Контент рендерится в контейнере --- */}
                 <Container maxWidth="xl" sx={{ mt: 4 }}>
                     {pageContent}
                 </Container>
            </Box>
        </>
    );
}