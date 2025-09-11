// frontend/src/pages/Home/components/CtaSection.js
import React from 'react';
import { Paper, Typography, Box, Button, alpha } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { motion } from 'framer-motion';

const CtaSection = () => {
    return (
        <Paper 
            sx={{ 
                p: {xs: 4, md: 8}, 
                textAlign: 'center', 
                borderRadius: 4, 
                position: 'relative',
                overflow: 'hidden',
                background: (theme) => `radial-gradient(circle, ${alpha(theme.palette.primary.dark, 0.5)} 0%, ${theme.palette.background.paper} 70%)`
            }}
        >
            <Box 
                component={motion.div}
                initial={{ scale: 0, opacity: 0}}
                whileInView={{ scale: [1, 1.5, 1], opacity: [0.1, 0.05, 0.1]}}
                transition={{ duration: 15, repeat: Infinity, repeatType: 'mirror' }}
                sx={{ 
                    position: 'absolute', 
                    top: '50%', left: '50%', 
                    width: '400px', height: '400px',
                    borderRadius: '50%',
                    transform: 'translate(-50%, -50%)',
                    background: (theme) => `linear-gradient(45deg, ${theme.palette.primary.main} 30%, ${theme.palette.secondary.main} 90%)`,
                }}
            />
            <Box 
                sx={{ 
                    position: 'relative', 
                    zIndex: 1, 
                    p: { xs: 2, sm: 4 },
                    borderRadius: 3,
                    backgroundColor: 'rgba(13, 14, 18, 0.5)',
                    backdropFilter: 'blur(10px)',
                    border: '1px solid',
                    borderColor: 'divider'
                }}
                component={motion.div} 
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.5 }}
                transition={{ duration: 0.7 }}
            >
                <Typography variant="h3" component="h2" sx={{ fontWeight: 700, color: 'white' }}>Готовы к росту?</Typography>
                <Typography variant="h6" sx={{ my: 3, color: 'text.secondary', maxWidth: '600px', mx: 'auto' }}>
                    Присоединяйтесь к Zenith сегодня и начните свой путь к эффективному SMM.
                </Typography>
                 <Button 
                    variant="contained" 
                    size="large" 
                    component={RouterLink} 
                    to="/login"
                    sx={{
                        fontSize: '1.1rem',
                        px: 5
                    }}
                >
                    Начать использовать
                </Button>
            </Box>
        </Paper>
    );
};

export default CtaSection;