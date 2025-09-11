// frontend/src/pages/Home/components/StepsSection.js
import React from 'react';
import { Grid, Typography, Container } from '@mui/material';
import { motion } from 'framer-motion';
import StepCard from './StepCard';

// Иконки
import ShieldOutlinedIcon from '@mui/icons-material/ShieldOutlined';
import TuneOutlinedIcon from '@mui/icons-material/TuneOutlined';
import AnalyticsOutlinedIcon from '@mui/icons-material/AnalyticsOutlined';

const stepsData = [
    { num: "1", icon: <ShieldOutlinedIcon fontSize="inherit" />, title: "Безопасная авторизация", desc: "Получите временный ключ доступа VK. Мы никогда не запрашиваем и не храним ваш логин и пароль." },
    { num: "2", icon: <TuneOutlinedIcon fontSize="inherit" />, title: "Гибкая настройка", desc: "Выберите действие, настройте мощные фильтры или создайте собственный сценарий работы по расписанию." },
    { num: "3", icon: <AnalyticsOutlinedIcon fontSize="inherit" />, title: "Анализ и контроль", desc: "Наблюдайте за выполнением каждой операции в реальном времени и отслеживайте рост вашего аккаунта." },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const StepsSection = () => {
    return (
        <Container maxWidth="lg">
            <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.3 }}>
                <motion.div variants={fadeInUp}>
                    <Typography variant="h3" component="h2" textAlign="center" gutterBottom sx={{ mb: 8, fontWeight: 700 }}>
                        Всего 3 шага к результату
                    </Typography>
                </motion.div>
                <Grid container spacing={4} alignItems="stretch">
                    {stepsData.map((step) => (
                        <Grid item xs={12} md={4} key={step.num}>
                             <StepCard {...step} />
                        </Grid>
                    ))}
                </Grid>
            </motion.div>
        </Container>
    );
};

export default StepsSection;