// frontend/src/components/Footer.js
import React from 'react';
import { Box, Container, Typography, Stack, Link } from '@mui/material';
import TrackChangesIcon from '@mui/icons-material/TrackChanges';
import { content } from 'content/content';

const FooterLink = ({ href, children }) => (
    <Link 
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        variant="body2" 
        sx={{ 
            color: 'text.secondary', 
            textDecoration: 'none', 
            transition: 'color 0.2s ease-in-out',
            '&:hover': { color: 'primary.main' }
        }}
    >
        {children}
    </Link>
);

export default function Footer() {
    return (
        <Box component="footer" sx={{ py: 4, mt: 'auto', backgroundColor: 'background.paper', borderTop: 1, borderColor: 'divider' }}>
            <Container maxWidth="xl">
                <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems="center" spacing={2}>
                    <Stack direction="row" alignItems="center" spacing={1.5}>
                        <TrackChangesIcon color="primary" />
                        <Typography variant="body1" fontWeight={600}>{content.appName}</Typography>
                        <Typography variant="body2" color="text.secondary">© {new Date().getFullYear()}</Typography>
                    </Stack>
                    <Stack direction="row" spacing={3} alignItems="center">
                        <FooterLink href="#">Политика конфиденциальности</FooterLink>
                        <FooterLink href="#">Условия использования</FooterLink>
                    </Stack>
                </Stack>
            </Container>
        </Box>
    );
}