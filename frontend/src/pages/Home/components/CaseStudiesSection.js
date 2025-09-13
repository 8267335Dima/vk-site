// frontend/src/pages/Home/components/CaseStudiesSection.js
import React from 'react';
import { Typography, Grid, Paper, Stack, Box, Chip, alpha } from '@mui/material';
import { motion } from 'framer-motion';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import AccessAlarmIcon from '@mui/icons-material/AccessAlarm';

const caseStudiesData = [
  {
    icon: <TrendingUpIcon fontSize="large" />,
    chip: "SMM-Агентство",
    title: "Рост охвата клиента на 270%",
    description: "С помощью гибких сценариев и авто-лайков наш клиент, SMM-агентство, добилось трехкратного роста вовлеченности для своего заказчика в сфере ритейла за 2 месяца.",
    color: "primary"
  },
  {
    icon: <GroupAddIcon fontSize="large" />,
    chip: "Малый бизнес",
    title: "+1200 целевых подписчиков",
    description: "Владелец локальной кофейни использовал авто-добавление по рекомендациям с фильтрацией по городу, что привело к значительному увеличению числа реальных посетителей.",
    color: "secondary"
  },
  {
    icon: <AccessAlarmIcon fontSize="large" />,
    chip: "Частный специалист",
    title: "Экономия 8+ часов в неделю",
    description: "Фотограф полностью автоматизировал прием заявок, поздравления и поддержание активности на странице, высвободив целый рабочий день для творчества и съемок.",
    color: "success"
  },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0, scale: 0.95 },
    animate: { y: 0, opacity: 1, scale: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const CaseStudyCard = ({ icon, chip, title, description, color }) => (
    <motion.div variants={fadeInUp} style={{ height: '100%' }}>
        <Paper 
            sx={{ 
                p: 3, 
                height: '100%',
                display: 'flex', 
                flexDirection: 'column',
                borderColor: `${color}.main`,
                background: (theme) => `radial-gradient(circle at 0% 0%, ${alpha(theme.palette[color].main, 0.1)}, ${theme.palette.background.paper} 40%)`
            }}
        >
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
                <Box sx={{ color: `${color}.main`, mb: 2 }}>{icon}</Box>
                <Chip label={chip} color={color} variant="outlined" size="small"/>
            </Stack>
            <Typography variant="h5" sx={{ fontWeight: 700, mb: 1.5, flexGrow: 1 }}>{title}</Typography>
            <Typography color="text.secondary">{description}</Typography>
        </Paper>
    </motion.div>
);

const CaseStudiesSection = () => {
    return (
        <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.2 }}>
            <motion.div variants={fadeInUp}>
                <Typography variant="h3" component="h2" textAlign="center" sx={{ mb: 2, fontWeight: 700 }}>
                    Результаты, а не обещания
                </Typography>
                <Typography variant="h6" color="text.secondary" textAlign="center" sx={{ mb: 8, maxWidth: '700px', mx: 'auto' }}>
                    Zenith — это не просто инструмент. Это катализатор роста для реальных людей и бизнесов.
                </Typography>
            </motion.div>
            <Grid container spacing={4} alignItems="stretch">
                {caseStudiesData.map((study, i) => (
                    <Grid item xs={12} md={4} key={i}>
                        <CaseStudyCard {...study} />
                    </Grid>
                ))}
            </Grid>
        </motion.div>
    );
};

export default CaseStudiesSection;