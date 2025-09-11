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