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
                    <Grid item xs={12} md={4}>
                        <Stack spacing={2} alignItems={{xs: 'center', md: 'flex-start'}}>
                            <Stack direction="row" alignItems="center" spacing={1.5}>
                                <TrackChangesIcon color="primary" sx={{ fontSize: '2.5rem' }} />
                                <Typography variant="h5" sx={{ color: 'text.primary', fontWeight: 700 }}>
                                    {content.appName}
                                </Typography>
                            </Stack>
                            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 300, textAlign: {xs: 'center', md: 'left'} }}>
                                Интеллектуальная платформа для автоматизации и роста в социальных сетях.
                            </Typography>
                        </Stack>
                    </Grid>
                    <Grid item xs={6} sm={4} md={2}>
                        <Stack spacing={1} alignItems={{xs: 'center', md: 'flex-start'}}>
                            <FooterTitle>Продукт</FooterTitle>
                            <FooterLink to="/dashboard">Кабинет</FooterLink>
                            <FooterLink to="/scenarios">Сценарии</FooterLink>
                            <FooterLink to="/billing">Тарифы</FooterLink>
                        </Stack>
                    </Grid>
                    <Grid item xs={6} sm={4} md={3}>
                         <Stack spacing={1} alignItems={{xs: 'center', md: 'flex-start'}}>
                            <FooterTitle>Ресурсы</FooterTitle>
                            <FooterLink href="#">Политика конфиденциальности</FooterLink>
                            <FooterLink href="#">Условия использования</FooterLink>
                            <FooterLink href="#">База знаний</FooterLink>
                        </Stack>
                    </Grid>
                    <Grid item xs={12} sm={4} md={3}>
                         <Stack spacing={1} alignItems={{xs: 'center', md: 'flex-start'}}>
                            <FooterTitle>Контакты</FooterTitle>
                            <FooterLink href="#">Telegram-канал</FooterLink>
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