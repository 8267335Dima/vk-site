// --- frontend/src/pages/Home/components/AdvantageSection.js ---
import React from 'react';
import { Typography, Stack, Paper, alpha, useTheme, Grid } from '@mui/material';
import { motion } from 'framer-motion';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SecurityIcon from '@mui/icons-material/Security';
import TimerIcon from '@mui/icons-material/Timer';

const projectionData = [
  { name: 'Старт', 'Охват': 350, 'Подписчики': 1000 },
  { name: 'Неделя 1', 'Охват': 520, 'Подписчики': 1015 },
  { name: 'Неделя 2', 'Охват': 810, 'Подписчики': 1045 },
  { name: 'Неделя 3', 'Охват': 1350, 'Подписчики': 1110 },
  { name: 'Неделя 4', 'Охват': 2280, 'Подписчики': 1250 },
  { name: 'Неделя 5', 'Охват': 3450, 'Подписчики': 1480 },
  { name: 'Неделя 6', 'Охват': 5250, 'Подписчики': 1800 },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
        return (
            <Paper sx={{ p: 2, background: 'rgba(30, 31, 37, 0.9)', backdropFilter: 'blur(5px)', borderRadius: 2 }}>
                <Typography variant="body2" sx={{ mb: 1, fontWeight: 600 }}>{label}</Typography>
                {payload.map(p => (
                    <Typography key={p.name} variant="body2" sx={{ color: p.color }}>
                        {`${p.name}: ${p.value.toLocaleString('ru-RU')}`}
                    </Typography>
                ))}
            </Paper>
        );
    }
    return null;
};


const AdvantageSection = () => {
    const theme = useTheme();

    return (
        <Grid container spacing={6} alignItems="center">
            <Grid item xs={12} md={5}>
                 <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.5 }}>
                    <motion.div variants={fadeInUp}>
                        <Typography variant="h3" component="h2" sx={{ fontWeight: 700, mb: 2 }}>
                           Ваше технологическое преимущество
                        </Typography>
                        <Typography variant="h6" color="text.secondary" sx={{ mb: 4 }}>
                            Мы объединили поведенческую эмуляцию и data-driven подход, чтобы вы получали измеримый и органический результат.
                        </Typography>
                    </motion.div>
                    <Stack spacing={3}>
                        <motion.div variants={fadeInUp}>
                            <Stack direction="row" spacing={2}><SecurityIcon color="primary"/><Typography><b>Безопасность — наш приоритет:</b> работа через временный API-ключ и поддержка персональных прокси для полной анонимности.</Typography></Stack>
                        </motion.div>
                        <motion.div variants={fadeInUp}>
                            <Stack direction="row" spacing={2}><AutoAwesomeIcon color="primary"/><Typography><b>Интеллектуальная имитация:</b> алгоритм Humanizer™ делает автоматизацию неотличимой от ручной работы, соблюдая динамические лимиты VK.</Typography></Stack>
                        </motion.div>
                         <motion.div variants={fadeInUp}>
                            <Stack direction="row" spacing={2}><TimerIcon color="primary"/><Typography><b>Облачная инфраструктура 24/7:</b> настройте сценарии один раз, и Zenith будет работать на вас круглосуточно, даже когда вы оффлайн.</Typography></Stack>
                        </motion.div>
                    </Stack>
                 </motion.div>
            </Grid>
            <Grid item xs={12} md={7}>
                <motion.div initial={{ opacity: 0, scale: 0.9 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true, amount: 0.5 }} transition={{ duration: 0.7 }}>
                     <Paper sx={{ p: {xs: 2, sm: 3}, height: 400, display: 'flex', flexDirection: 'column' }}>
                         <Typography variant="h6" sx={{ fontWeight: 600 }}>Прогнозируемый рост</Typography>
                         <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Пример влияния регулярной активности на видимость профиля.</Typography>
                         <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={projectionData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" stroke={alpha("#A0A3BD", 0.1)} />
                                <XAxis dataKey="name" stroke="#A0A3BD" fontSize="0.8rem" />
                                <YAxis yAxisId="left" stroke={theme.palette.primary.main} fontSize="0.8rem" />
                                <YAxis yAxisId="right" orientation="right" stroke={theme.palette.secondary.main} fontSize="0.8rem" />
                                <Tooltip content={<CustomTooltip />} />
                                <Legend />
                                <Line yAxisId="left" type="monotone" dataKey="Охват" stroke={theme.palette.primary.main} strokeWidth={3} dot={{ r: 4, strokeWidth: 2, fill: theme.palette.background.paper }} activeDot={{ r: 8 }}/>
                                <Line yAxisId="right" type="monotone" dataKey="Подписчики" stroke={theme.palette.secondary.main} strokeWidth={3} dot={{ r: 4, strokeWidth: 2, fill: theme.palette.background.paper }} activeDot={{ r: 8 }}/>
                            </LineChart>
                         </ResponsiveContainer>
                     </Paper>
                </motion.div>
            </Grid>
        </Grid>
    );
};

export default AdvantageSection;