// --- frontend/src/pages/Forbidden/ForbiddenPage.js ---
import React from 'react';
import { Box, Paper, Typography, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import BlockIcon from '@mui/icons-material/Block';
import { motion } from 'framer-motion';

const ForbiddenPage = () => {
    return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh' }}>
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
                <Paper sx={{ p: 4, textAlign: 'center', maxWidth: 500 }}>
                    <BlockIcon color="error" sx={{ fontSize: 60, mb: 2 }}/>
                    <Typography variant="h5" component="h1" gutterBottom sx={{ fontWeight: 600 }}>
                        Доступ ограничен
                    </Typography>
                    <Typography color="text.secondary" sx={{ mb: 3 }}>
                        Эта страница или функция недоступна на вашем текущем тарифном плане. Пожалуйста, обновите тариф, чтобы получить доступ.
                    </Typography>
                    <Button 
                        variant="contained" 
                        component={RouterLink}
                        to="/billing"
                    >
                        Перейти к тарифам
                    </Button>
                </Paper>
            </motion.div>
        </Box>
    );
};

export default ForbiddenPage;