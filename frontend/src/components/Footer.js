// frontend/src/components/Footer.js
import React from 'react';
import { Box, Container, Typography, Stack, Link } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import { content } from 'content/content';

const FooterLink = ({ to, children }) => (
    <Link component={RouterLink} to={to} variant="body2" sx={{ color: 'text.secondary', textDecoration: 'none', '&:hover': { color: 'primary.main' }}}>
        {children}
    </Link>
);

export default function Footer() {
    return (
        <Box component="footer" sx={{ py: 4, mt: 'auto', backgroundColor: 'rgba(23, 24, 29, 0.5)', borderTop: 1, borderColor: 'divider' }}>
            <Container maxWidth="xl">
                <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems="center" spacing={2}>
                    <Stack direction="row" alignItems="center" spacing={1}>
                        <TrackChangesIcon color="primary" />
                        <Typography variant="body1" fontWeight={600}>{content.appName}</Typography>
                        <Typography variant="body2" color="text.secondary">© {new Date().getFullYear()}</Typography>
                    </Stack>
                    <Stack direction="row" spacing={3}>
                        <FooterLink to="/">Главная</FooterLink>
                        <FooterLink to="/billing">Тарифы</FooterLink>
                        <Link href="#" variant="body2" sx={{ color: 'text.secondary', textDecoration: 'none', '&:hover': { color: 'primary.main' }}}>
                            Политика конфиденциальности
                        </Link>
                    </Stack>
                </Stack>
            </Container>
        </Box>
    );
}