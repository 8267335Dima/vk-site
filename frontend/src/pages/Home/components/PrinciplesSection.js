// frontend/src/pages/Home/components/PrinciplesSection.js
import React from 'react';
import { Typography, Grid, Stack, Box } from '@mui/material';
import { motion } from 'framer-motion';
import VerifiedUserOutlinedIcon from '@mui/icons-material/VerifiedUserOutlined';
import PriceCheckOutlinedIcon from '@mui/icons-material/PriceCheckOutlined';
import RocketLaunchOutlinedIcon from '@mui/icons-material/RocketLaunchOutlined';
import CodeOutlinedIcon from '@mui/icons-material/CodeOutlined';

const principlesData = [
    { icon: <VerifiedUserOutlinedIcon sx={{ fontSize: 40 }}/>, title: "Безопасность прежде всего", text: "Мы никогда не запрашиваем ваш пароль. Работа через API-токен и умный алгоритм Humanizer™ гарантируют защиту вашего аккаунта." },
    { icon: <RocketLaunchOutlinedIcon sx={{ fontSize: 40 }}/>, title: "Максимальная эффективность", text: "Наши инструменты, от сценариев до фильтров, созданы для достижения измеримых результатов, а не просто для имитации активности." },
    { icon: <PriceCheckOutlinedIcon sx={{ fontSize: 40 }}/>, title: "Честная цена", text: "Мы верим, что мощные SMM-технологии должны быть доступны каждому. Вы получаете максимум функций без скрытых платежей." },
    { icon: <CodeOutlinedIcon sx={{ fontSize: 40 }}/>, title: "Постоянное развитие", text: "Мы регулярно обновляем платформу, добавляя новые возможности и адаптируясь к изменениям алгоритмов ВКонтакте." },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};

const PrinciplesSection = () => {
    return (
        <Box>
            <motion.div initial="initial" whileInView="animate" variants={fadeInUp} viewport={{ once: true, amount: 0.5 }}>
                <Typography variant="h3" component="h2" textAlign="center" sx={{ mb: 8, fontWeight: 700 }}>
                    Наша философия
                </Typography>
            </motion.div>
            <Grid container spacing={5}>
                {principlesData.map((item, i) => (
                    <Grid item xs={12} md={6} key={i}>
                        <motion.div initial="initial" whileInView="animate" variants={fadeInUp} viewport={{ once: true, amount: 0.5 }}>
                            <Stack direction="row" spacing={3}>
                                <Box sx={{ color: 'primary.main', mt: 0.5 }}>{item.icon}</Box>
                                <Box>
                                    <Typography variant="h5" sx={{ fontWeight: 600, mb: 1 }}>{item.title}</Typography>
                                    <Typography color="text.secondary">{item.text}</Typography>
                                </Box>
                            </Stack>
                        </motion.div>
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};

export default PrinciplesSection;