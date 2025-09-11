// frontend/src/pages/Home/components/HeroSection.js
import React from 'react';
import { Container, Typography, Button, Box } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { motion } from 'framer-motion';

const HeroSection = () => {
  return (
    <Container maxWidth="lg">
      <motion.div initial={{ opacity: 0, y: -30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
        <Typography 
          variant="h1" 
          component="h1" 
          sx={{
            fontWeight: 800, 
            textAlign: 'center', 
            background: (theme) => `linear-gradient(45deg, ${theme.palette.primary.main} 30%, ${theme.palette.secondary.main} 90%)`,
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          Интеллектуальная SMM-платформа
        </Typography>
        <Typography variant="h5" color="text.secondary" paragraph sx={{ mt: 2, mb: 4, maxWidth: '750px', mx: 'auto', textAlign: 'center' }}>
          Zenith — это ваш персональный ассистент для ВКонтакте, созданный для органического роста, повышения охватов и тотальной автоматизации рутины.
        </Typography>
        <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.4, duration: 0.5 }}>
          <Box sx={{ display: 'flex', justifyContent: 'center' }}>
              <Button variant="contained" size="large" component={RouterLink} to="/login" sx={{py: 1.5, px: 5, fontSize: '1.1rem'}}>
                  Начать бесплатно
              </Button>
          </Box>
        </motion.div>
      </motion.div>
    </Container>
  );
};

export default HeroSection;