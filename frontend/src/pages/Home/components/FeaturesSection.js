// frontend/src/pages/Home/components/FeaturesSection.js
import React from 'react';
import { Grid, Typography, Container } from '@mui/material';
import { motion } from 'framer-motion';
import FeatureHighlightCard from './FeatureHighlightCard';

// Иконки
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import BarChartOutlinedIcon from '@mui/icons-material/BarChartOutlined';
import VpnKeyOutlinedIcon from '@mui/icons-material/VpnKeyOutlined';
import CloudQueueOutlinedIcon from '@mui/icons-material/CloudQueueOutlined';
import FilterAltOutlinedIcon from '@mui/icons-material/FilterAltOutlined';

// Данные для этого компонента теперь хранятся здесь же
const featuresData = [
    { icon: <HubOutlinedIcon />, title: "Продвинутые сценарии", description: "Создавайте сложные цепочки действий, которые будут выполняться по вашему расписанию 24/7." },
    { icon: <PsychologyOutlinedIcon />, title: "Алгоритм Humanizer™", description: "Интеллектуальные задержки между действиями имитируют поведение человека, минимизируя риски." },
    { icon: <BarChartOutlinedIcon />, title: "Live-аналитика", description: "Отслеживайте динамику роста друзей, подписчиков и охватов на наглядных графиках." },
    { icon: <VpnKeyOutlinedIcon />, title: "Поддержка Proxy", description: "Используйте собственные прокси-серверы для максимальной анонимности и безопасности аккаунта." },
    { icon: <CloudQueueOutlinedIcon />, title: "Облачная работа", description: "Все задачи выполняются на наших серверах. Вам не нужно держать компьютер включенным." },
    { icon: <FilterAltOutlinedIcon />, title: "Детальная фильтрация", description: "Таргетируйте аудиторию по полу, онлайну, активности и другим критериям для максимальной эффективности." },
];

// Анимации
const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const FeaturesSection = () => {
  return (
    <Container maxWidth="lg">
      <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.2 }}>
          <motion.div variants={fadeInUp}>
               <Typography variant="h3" component="h2" textAlign="center" sx={{ mb: 8, fontWeight: 700 }}>
                  Все инструменты для доминирования в SMM
              </Typography>
          </motion.div>
          <Grid container spacing={5}>
              {featuresData.map((feature, i) => (
                  <Grid item xs={12} md={6} lg={4} key={i}>
                      <FeatureHighlightCard {...feature} />
                  </Grid>
              ))}
          </Grid>
      </motion.div>
    </Container>
  );
};

export default FeaturesSection;