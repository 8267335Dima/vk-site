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
                        top: '-30px',
                        left: '0px',
                        fontWeight: 800,
                        fontSize: '9rem',
                        lineHeight: 1,
                        color: (theme) => alpha(theme.palette.text.primary, 0.04),
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