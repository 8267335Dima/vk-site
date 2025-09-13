// frontend/src/pages/Home/components/HeroSection.js
import React from 'react';
import { Container, Typography, Button, Stack } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { motion } from 'framer-motion';

const HeroSection = () => {
  return (
    <Container maxWidth="lg" sx={{ textAlign: 'center' }}>
      <motion.div
        initial="hidden"
        animate="visible"
        variants={{
          hidden: { opacity: 0 },
          visible: { opacity: 1, transition: { staggerChildren: 0.2 } },
        }}
      >
        <motion.div variants={{ hidden: { opacity: 0, y: -20 }, visible: { opacity: 1, y: 0, transition: { duration: 0.7 } } }}>
          <Typography 
            variant="h2"
            component="h1" 
            sx={{
              fontWeight: 800,
              maxWidth: '850px',
              mx: 'auto',
              background: (theme) => `linear-gradient(45deg, ${theme.palette.primary.main} 30%, ${theme.palette.secondary.main} 90%)`,
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            {/* --- ИЗМЕНЕНИЕ: Текст стал более профессиональным --- */}
            Интеллектуальная платформа для продвижения ВКонтакте
          </Typography>
        </motion.div>
        <motion.div variants={{ hidden: { opacity: 0, y: 20 }, visible: { opacity: 1, y: 0, transition: { duration: 0.7, delay: 0.2 } } }}>
          <Typography variant="h6" color="text.secondary" paragraph sx={{ mt: 3, mb: 4, maxWidth: '750px', mx: 'auto' }}>
            {/* --- ИЗМЕНЕНИЕ: Описание стало более конкретным --- */}
            Zenith — это ваш надежный партнер для органического роста, повышения охватов и комплексной автоматизации рутинных SMM-задач. Сосредоточьтесь на контенте, а мы позаботимся о его продвижении.
          </Typography>
        </motion.div>
        <motion.div variants={{ hidden: { scale: 0.8, opacity: 0 }, visible: { scale: 1, opacity: 1, transition: { duration: 0.5, delay: 0.4 } } }}>
          <Stack direction={{xs: 'column', sm: 'row'}} spacing={2} justifyContent="center">
              <Button variant="contained" size="large" component={RouterLink} to="/login" sx={{py: 1.5, px: 5, fontSize: '1.1rem'}}>
                  Начать бесплатно (14 дней)
              </Button>
              {/* --- ИЗМЕНЕНИЕ: Кнопка теперь ведет на страницу тарифов --- */}
              <Button variant="outlined" size="large" component={RouterLink} to="/billing" sx={{py: 1.5, px: 5, fontSize: '1.1rem'}}>
                  Смотреть тарифы
              </Button>
          </Stack>
        </motion.div>
      </motion.div>
    </Container>
  );
};

export default HeroSection;