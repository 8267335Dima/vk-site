import React from 'react';
import { Grid, Typography, Paper, Box, alpha } from '@mui/material';
import { motion } from 'framer-motion';
import StorefrontIcon from '@mui/icons-material/Storefront';
import BrushIcon from '@mui/icons-material/Brush';
import CampaignIcon from '@mui/icons-material/Campaign';

const audienceData = [
  {
    icon: <CampaignIcon />,
    title: 'SMM-специалистам и агентствам',
    description:
      'Автоматизируйте рутину по всем клиентским проектам, экономьте часы работы и предоставляйте отчеты на основе реальной динамики роста.',
    color: 'primary',
  },
  {
    icon: <BrushIcon />,
    title: 'Блогерам и экспертам',
    description:
      'Наращивайте лояльную аудиторию, повышайте вовлеченность и охваты, поддерживая постоянную активность на странице без усилий.',
    color: 'secondary',
  },
  {
    icon: <StorefrontIcon />,
    title: 'Малому и локальному бизнесу',
    description:
      'Привлекайте целевых клиентов из вашего города, информируйте их о новинках и повышайте узнаваемость бренда в соцсетях.',
    color: 'success',
  },
];

const fadeInUp = {
  initial: { y: 40, opacity: 0, scale: 0.95 },
  animate: {
    y: 0,
    opacity: 1,
    scale: 1,
    transition: { type: 'spring', stiffness: 100, damping: 20, duration: 0.8 },
  },
};
const staggerContainer = {
  animate: { transition: { staggerChildren: 0.15 } },
};

const AudienceCard = ({ icon, title, description, color }) => (
  <motion.div variants={fadeInUp} style={{ height: '100%' }}>
    <Paper
      sx={{
        p: 3,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        textAlign: 'center',
        alignItems: 'center',
        borderColor: `${color}.main`,
        background: (theme) =>
          `radial-gradient(circle at 50% 0%, ${alpha(
            theme.palette[color].dark,
            0.1
          )}, ${theme.palette.background.paper} 50%)`,
      }}
    >
      <Box sx={{ color: `${color}.main`, fontSize: '3rem', mb: 2 }}>{icon}</Box>
      <Typography variant="h5" sx={{ fontWeight: 700, mb: 1.5 }}>
        {title}
      </Typography>
      <Typography color="text.secondary">{description}</Typography>
    </Paper>
  </motion.div>
);

const TargetAudienceSection = () => {
  return (
    <motion.div
      initial="initial"
      whileInView="animate"
      variants={staggerContainer}
      viewport={{ once: true, amount: 0.2 }}
    >
      <motion.div variants={fadeInUp}>
        <Typography
          variant="h3"
          component="h2"
          textAlign="center"
          sx={{ mb: 2, fontWeight: 700 }}
        >
          Для кого подходит Zenith?
        </Typography>
        <Typography
          variant="h6"
          color="text.secondary"
          textAlign="center"
          sx={{ mb: 8, maxWidth: '700px', mx: 'auto' }}
        >
          Наша платформа создана для всех, кто хочет использовать ВКонтакте как
          эффективный канал для достижения своих целей.
        </Typography>
      </motion.div>
      <Grid container spacing={4} alignItems="stretch">
        {audienceData.map((audience, i) => (
          <Grid item xs={12} md={4} key={i}>
            <AudienceCard {...audience} />
          </Grid>
        ))}
      </Grid>
    </motion.div>
  );
};

export default TargetAudienceSection;
