// frontend/src/pages/Home/HomePage.js
import React from 'react';
import { Container, Typography, Button, Box, Grid, Stack, Paper, alpha } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import { heroSection, featureList, benefitsSection, howItWorksSection, ctaSection, algorithmsSection } from 'content/homePageContent';
// --- ИКОНКА ДЛЯ ЗАМЕНЫ КАРТИНКИ ---
import QueryStatsIcon from '@mui/icons-material/QueryStats';

// Варианты анимации для карточек при появлении на экране
const cardVariants = {
    offscreen: { y: 50, opacity: 0 },
    onscreen: { y: 0, opacity: 1, transition: { type: "spring", bounce: 0.4, duration: 0.8 } }
};

// Обёртка для секций, чтобы не дублировать стили
const SectionWrapper = ({ children, background = 'transparent', py = { xs: 8, md: 12 } }) => (
    <Box sx={{ py, backgroundColor: background, overflow: 'hidden' }}>
        <Container maxWidth="lg">{children}</Container>
    </Box>
);

export default function HomePage() {
  return (
    <Box>
      {/* Секция 1: Главный экран */}
      <SectionWrapper py={{ xs: 12, md: 20 }}>
        <motion.div initial={{ opacity: 0, y: -50 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
          <Typography variant="h1" component="h1" gutterBottom sx={{fontWeight: 800, textAlign: 'center' }}>
            {heroSection.title}
          </Typography>
          <Typography variant="h5" color="text.secondary" paragraph sx={{ mb: 4, maxWidth: '750px', mx: 'auto', textAlign: 'center' }}>
            {heroSection.subtitle}
          </Typography>
          <Box sx={{ display: 'flex', justifyContent: 'center' }}>
            <Button variant="contained" size="large" component={RouterLink} to="/dashboard" sx={{py: 1.5, px: 5, fontSize: '1.1rem'}}>
                {heroSection.ctaButton}
            </Button>
          </Box>
        </motion.div>
      </SectionWrapper>

      {/* Секция 2: Ключевые особенности (иконки) */}
      <SectionWrapper>
          <Grid container spacing={4}>
              {featureList.map((f, i) => (
                <Grid item xs={6} sm={4} md={2} key={`feat-${i}`} >
                    <motion.div initial="offscreen" whileInView="onscreen" viewport={{ once: true, amount: 0.5 }} transition={{ delay: i * 0.1 }} variants={cardVariants}>
                        <Paper variant="outlined" sx={{ display: 'flex', alignItems: 'center', flexDirection: 'column', gap: 1.5, p: 2, borderRadius: 4, height: '100%', textAlign: 'center', bgcolor: 'transparent' }}>
                            <Box sx={{color: 'primary.main', fontSize: '2.5rem'}}>{f.icon}</Box>
                            <Typography fontWeight={500}>{f.title}</Typography>
                        </Paper>
                    </motion.div>
                </Grid>
              ))}
          </Grid>
      </SectionWrapper>

      {/* Секция 3: Преимущества с ЗАМЕНОЙ картинки */}
      <SectionWrapper background={(theme) => alpha(theme.palette.primary.main, 0.05)}>
          <Typography variant="h3" component="h2" textAlign="center" gutterBottom sx={{ fontWeight: 600, mb: 2 }}>
              {benefitsSection.title}
          </Typography>
          <Typography variant="h6" color="text.secondary" textAlign="center" paragraph sx={{ mb: 8, maxWidth: '850px', mx: 'auto' }}>
              {benefitsSection.subtitle}
          </Typography>
          <Grid container spacing={5} alignItems="center">
              <Grid item xs={12} md={6}>
                  <Stack spacing={4}>
                      {benefitsSection.benefits.map((b, i) => (
                           <motion.div key={`bene-${i}`} initial="offscreen" whileInView="onscreen" viewport={{ once: true, amount: 0.5 }} variants={cardVariants}>
                              <Box sx={{display: 'flex', alignItems: 'flex-start', gap: 2.5}}>
                                  <Box sx={{fontSize: '2.5rem', mt: 0.5, color: 'primary.main'}}>{b.icon}</Box>
                                  <Box>
                                      <Typography variant="h6" sx={{fontWeight: 600}}>{b.title}</Typography>
                                      <Typography color="text.secondary">{b.description}</Typography>
                                  </Box>
                              </Box>
                          </motion.div>
                      ))}
                  </Stack>
              </Grid>
              <Grid item xs={12} md={6}>
                  <motion.div initial={{ opacity: 0, scale: 0.8 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true, amount: 0.5 }} transition={{ duration: 0.7 }}>
                      {/* --- НАЧАЛО БЛОКА ЗАМЕНЫ ОТСУТСТВУЮЩЕЙ КАРТИНКИ --- */}
                      <Paper
                          variant="outlined"
                          sx={{
                              aspectRatio: '4 / 3',
                              borderRadius: 4,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              flexDirection: 'column',
                              gap: 2,
                              p: 4,
                              backgroundColor: 'rgba(255, 255, 255, 0.03)',
                              borderStyle: 'dashed',
                              borderColor: 'divider',
                              transition: 'border-color 0.3s, box-shadow 0.3s',
                              '&:hover': {
                                  borderColor: 'primary.main',
                                  boxShadow: (theme) => `0 0 30px ${theme.palette.primary.main}33`,
                              }
                          }}
                      >
                          <QueryStatsIcon sx={{ fontSize: '100px', color: 'primary.main' }} />
                          <Typography variant="h5" color="text.secondary" sx={{ fontWeight: 600 }}>
                              Dashboard Preview
                          </Typography>
                      </Paper>
                      {/* --- КОНЕЦ БЛОКА ЗАМЕНЫ --- */}
                  </motion.div>
              </Grid>
          </Grid>
      </SectionWrapper>

      {/* Секция 4: Как это работает */}
      <SectionWrapper>
          <Typography variant="h3" component="h2" textAlign="center" gutterBottom sx={{ mb: 8, fontWeight: 600 }}>
              {howItWorksSection.title}
          </Typography>
          <Grid container spacing={4} alignItems="stretch">
              {howItWorksSection.steps.map((step, i) => (
                  <Grid item xs={12} md={4} key={step.number}>
                       <motion.div initial="offscreen" whileInView="onscreen" viewport={{ once: true, amount: 0.5 }} transition={{ delay: i * 0.2 }} variants={cardVariants} style={{ textAlign: 'center', padding: '24px', height: '100%' }}>
                          <Typography variant="h1" color="primary.main" sx={{fontWeight: 800, opacity: 0.1}}>{step.number}</Typography>
                          <Typography variant="h5" sx={{mt: -4, fontWeight: 600}}>{step.title}</Typography>
                          <Typography color="text.secondary">{step.description}</Typography>
                      </motion.div>
                  </Grid>
              ))}
          </Grid>
      </SectionWrapper>
      
      {/* Секция 5: Алгоритмы */}
      <SectionWrapper background={(theme) => `radial-gradient(circle, ${alpha(theme.palette.primary.main, 0.1)} 0%, transparent 70%)`}>
          <Box sx={{textAlign: 'center', maxWidth: 'md', mx: 'auto'}}>
            <motion.div initial="offscreen" whileInView="onscreen" viewport={{ once: true, amount: 0.5 }} variants={cardVariants}>
                <Typography variant="h3" component="h2" gutterBottom sx={{ fontWeight: 600 }}> {algorithmsSection.title} </Typography>
                <Typography variant="h6" color="text.secondary" paragraph> {algorithmsSection.description} </Typography>
            </motion.div>
          </Box>
      </SectionWrapper>

      {/* Секция 6: Призыв к действию (CTA) */}
       <SectionWrapper>
        <Paper sx={{ p: {xs: 4, md: 8}, textAlign: 'center', backgroundImage: (theme) => `linear-gradient(45deg, ${theme.palette.primary.main} 30%, ${theme.palette.secondary.main} 90%)`, borderRadius: 4 }}>
            <motion.div initial="offscreen" whileInView="onscreen" viewport={{ once: true, amount: 0.5 }} variants={cardVariants}>
                <Typography variant="h3" component="h2" sx={{ fontWeight: 700, color: 'white' }}>{ctaSection.title}</Typography>
                <Typography variant="h6" sx={{ my: 3, color: 'rgba(255,255,255,0.8)' }}>{ctaSection.subtitle}</Typography>
                <Button variant="contained" size="large" component={RouterLink} to="/dashboard" sx={{ py: 1.5, px: 5, fontSize: '1.1rem', bgcolor: 'white', color: 'primary.main', '&:hover': { bgcolor: 'grey.200' }}}>
                    {ctaSection.ctaButton}
                </Button>
            </motion.div>
        </Paper>
      </SectionWrapper>
    </Box>
  );
}