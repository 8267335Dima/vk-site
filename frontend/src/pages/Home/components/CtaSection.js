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