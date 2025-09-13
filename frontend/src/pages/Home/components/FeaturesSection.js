// --- frontend/src/pages/Home/components/FeaturesSection.js ---
import React from 'react';
import { Grid, Typography } from '@mui/material';
import { motion } from 'framer-motion';
import FeatureHighlightCard from './FeatureHighlightCard';
import HubOutlinedIcon from '@mui/icons-material/HubOutlined';
import PsychologyOutlinedIcon from '@mui/icons-material/PsychologyOutlined';
import BarChartOutlinedIcon from '@mui/icons-material/BarChartOutlined';
import VpnKeyOutlinedIcon from '@mui/icons-material/VpnKeyOutlined';
import CloudQueueOutlinedIcon from '@mui/icons-material/CloudQueueOutlined';
import FilterAltOutlinedIcon from '@mui/icons-material/FilterAltOutlined';

const featuresData = [
    { icon: <HubOutlinedIcon />, title: "Продвинутые сценарии", description: "Комбинируйте действия в сложные цепочки и запускайте их по гибкому расписанию для достижения долгосрочных целей." },
    { icon: <PsychologyOutlinedIcon />, title: "Алгоритм Humanizer™", description: "Интеллектуальные задержки и вариативность действий имитируют поведение человека, минимизируя риски." },
    { icon: <BarChartOutlinedIcon />, title: "Live-аналитика", description: "Отслеживайте динамику роста друзей, подписчиков и охватов на наглядных графиках в реальном времени." },
    { icon: <VpnKeyOutlinedIcon />, title: "Поддержка Proxy", description: "Используйте собственные прокси-серверы для максимальной анонимности и обхода сетевых ограничений." },
    { icon: <CloudQueueOutlinedIcon />, title: "Облачная работа 24/7", description: "Все задачи выполняются на наших серверах. Вам не нужно держать компьютер или браузер включенным." },
    { icon: <FilterAltOutlinedIcon />, title: "Детальная фильтрация", description: "Таргетируйте аудиторию по десяткам критериев: от геолокации и онлайн-статуса до количества друзей." },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.15 } }
};

const FeaturesSection = () => {
  return (
      <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.2 }}>
          <motion.div variants={fadeInUp}>
               <Typography variant="h3" component="h2" textAlign="center" sx={{ mb: 8, fontWeight: 700 }}>
                  Профессиональный инструментарий для SMM
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
  );
};

export default FeaturesSection;