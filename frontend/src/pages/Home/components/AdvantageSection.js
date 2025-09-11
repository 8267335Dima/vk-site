// frontend/src/pages/Home/components/AdvantageSection.js
import React from 'react';
import { Grid, Typography, Stack, Paper, alpha, useTheme } from '@mui/material';
import { motion } from 'framer-motion';
import { XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart } from 'recharts';

// Иконки
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SecurityIcon from '@mui/icons-material/Security';
import TimerIcon from '@mui/icons-material/Timer';

// Данные для графика
const projectionData = [
  { name: 'Старт', 'Охват': 200 }, { name: 'Месяц 1', 'Охват': 220 }, { name: 'Месяц 2', 'Охват': 210 },
  { name: 'Месяц 3 (с Zenith)', 'Охват': 450 }, { name: 'Месяц 4', 'Охват': 680 }, { name: 'Месяц 5', 'Охват': 950 }, { name: 'Месяц 6', 'Охват': 1250 },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const AdvantageSection = () => {
    const theme = useTheme();

    return (
        <Grid container spacing={6} alignItems="center">
            <Grid item xs={12} lg={5}>
                <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.5 }}>
                   <motion.div variants={fadeInUp}>
                       <Typography variant="h3" component="h2" sx={{ fontWeight: 700, mb: 2 }}>
                          Ваше стратегическое преимущество
                        </Typography>
                        <Typography variant="h6" color="text.secondary" paragraph sx={{ mb: 4 }}>
                            Мы объединили передовые технологии и глубокое понимание алгоритмов, чтобы вы получали измеримый результат.
                        </Typography>
                   </motion.div>
                    <motion.div variants={fadeInUp}>
                        <Stack spacing={3}>
                            <Stack direction="row" spacing={2}><SecurityIcon color="primary"/><Typography><b>Безопасность — наш приоритет:</b> работа через временный токен VK и поддержка личных прокси.</Typography></Stack>
                            <Stack direction="row" spacing={2}><AutoAwesomeIcon color="primary"/><Typography><b>Интеллектуальная имитация:</b> алгоритм Humanizer™ делает автоматизацию неотличимой от ручной работы.</Typography></Stack>
                            <Stack direction="row" spacing={2}><TimerIcon color="primary"/><Typography><b>Автоматизация 24/7:</b> настройте сценарии один раз, и Zenith будет работать на вас круглосуточно.</Typography></Stack>
                        </Stack>
                    </motion.div>
                </motion.div>
            </Grid>
            <Grid item xs={12} lg={7}>
                 <motion.div initial={{ opacity: 0, scale: 0.9 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true, amount: 0.5 }} transition={{ duration: 0.7 }}>
                     <Paper sx={{ p: {xs: 2, sm: 3}, height: 400, display: 'flex', flexDirection: 'column' }}>
                         <Typography variant="h6" sx={{ fontWeight: 600 }}>Проекция роста охватов</Typography>
                         <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Пример влияния регулярной активности на видимость профиля.</Typography>
                         <ResponsiveContainer width="100%" height="100%">
                             <AreaChart data={projectionData} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                                 <defs>
                                     <linearGradient id="colorUv" x1="0" y1="0" x2="0" y2="1">
                                         <stop offset="5%" stopColor={theme.palette.secondary.main} stopOpacity={0.7}/>
                                         <stop offset="95%" stopColor={theme.palette.secondary.main} stopOpacity={0}/>
                                     </linearGradient>
                                 </defs>
                                 <XAxis dataKey="name" stroke="#A0A3BD" fontSize="0.8rem" />
                                 <YAxis stroke="#A0A3BD" fontSize="0.8rem"/>
                                 <CartesianGrid strokeDasharray="3 3" stroke={alpha("#A0A3BD", 0.1)} />
                                 <Tooltip contentStyle={{ backgroundColor: 'rgba(23, 24, 29, 0.8)', border: '1px solid #A0A3BD25', borderRadius: '12px', backdropFilter: 'blur(5px)' }}/>
                                 <Area type="monotone" dataKey="Охват" stroke={theme.palette.secondary.main} fillOpacity={1} fill="url(#colorUv)" strokeWidth={3} />
                             </AreaChart>
                         </ResponsiveContainer>
                     </Paper>
                 </motion.div>
            </Grid>
        </Grid>
    );
};

export default AdvantageSection;