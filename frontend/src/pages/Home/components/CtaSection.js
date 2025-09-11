// frontend/src/pages/Home/components/CtaSection.js
import React from 'react';
import { Paper, Typography, Box, Grid, alpha, useTheme } from '@mui/material';
import { motion } from 'framer-motion';
import { ResponsiveContainer, LineChart, Line, Tooltip as RechartsTooltip, RadialBarChart, RadialBar } from 'recharts';
import ThumbUpIcon from '@mui/icons-material/ThumbUp';
import ForumIcon from '@mui/icons-material/Forum';

const likesData = [
  { name: 'Неделя 1', value: 120 }, { name: 'Неделя 2', value: 250 },
  { name: 'Неделя 3', value: 480 }, { name: 'Неделя 4', value: 900 },
];
const messagesData = [{ name: 'Рост', value: 75 }];

const fadeInUp = {
    initial: { opacity: 0, y: 30 },
    animate: { opacity: 1, y: 0, transition: { duration: 0.7, ease: 'easeOut' } },
};

const EngagementChart = ({ icon, title, data, ChartComponent, children }) => (
    <Paper sx={{ p: 3, height: 200, display: 'flex', flexDirection: 'column', backgroundColor: 'rgba(13, 14, 18, 0.6)', backdropFilter: 'blur(10px)' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            {icon}
            <Typography sx={{ fontWeight: 600 }}>{title}</Typography>
        </Box>
        <ResponsiveContainer width="100%" height="100%">
            <ChartComponent data={data}>
                {children}
            </ChartComponent>
        </ResponsiveContainer>
    </Paper>
);

const CtaSection = () => {
    const theme = useTheme();
    return (
        <motion.div initial="initial" whileInView="animate" variants={fadeInUp} viewport={{ once: true, amount: 0.5 }}>
            <Paper 
                sx={{ 
                    p: { xs: 3, md: 5 }, 
                    textAlign: 'center', 
                    borderRadius: 4, 
                    position: 'relative',
                    overflow: 'hidden',
                    background: (theme) => `radial-gradient(ellipse at 50% 100%, ${alpha(theme.palette.primary.dark, 0.4)} 0%, ${theme.palette.background.default} 70%)`
                }}
            >
                <Typography variant="h3" component="h2" sx={{ fontWeight: 700, color: 'white' }}>
                    Превратите активность в популярность
                </Typography>
                <Typography variant="h6" sx={{ my: 3, color: 'text.secondary', maxWidth: '750px', mx: 'auto' }}>
                    Регулярные действия не просто увеличивают охваты. Они создают живое сообщество вокруг вас, стимулируя других пользователей к общению и проявлению симпатий.
                </Typography>
                <Grid container spacing={3} sx={{ mt: 4 }}>
                    <Grid item xs={12} md={8}>
                        <EngagementChart
                            icon={<ThumbUpIcon color="primary" />}
                            title="Рост полученных лайков"
                            data={likesData}
                            ChartComponent={LineChart}
                        >
                            <RechartsTooltip contentStyle={{ backgroundColor: 'rgba(23, 24, 29, 0.8)', border: '1px solid #A0A3BD25', borderRadius: '12px' }}/>
                            <Line type="monotone" dataKey="value" stroke={theme.palette.primary.main} strokeWidth={3} dot={false} />
                        </EngagementChart>
                    </Grid>
                    <Grid item xs={12} md={4}>
                        <EngagementChart
                            icon={<ForumIcon color="secondary" />}
                            title="Новых диалогов"
                            data={messagesData}
                            ChartComponent={RadialBarChart}
                        >
                            <RadialBar
                                background
                                dataKey="value"
                                cornerRadius={10}
                                fill={theme.palette.secondary.main}
                            />
                            <RechartsTooltip />
                        </EngagementChart>
                    </Grid>
                </Grid>
            </Paper>
        </motion.div>
    );
};

export default CtaSection;