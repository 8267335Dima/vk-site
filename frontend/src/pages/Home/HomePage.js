// frontend/src/pages/Home/HomePage.js
import React from 'react';
import { Container, Typography, Button, Box, Grid, Stack, Paper, alpha } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import { XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Area, AreaChart } from 'recharts';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import SecurityIcon from '@mui/icons-material/Security';
import TimerIcon from '@mui/icons-material/Timer';


// --- Данные для графика-проекции ---
const projectionData = [
  { name: 'Старт', 'Охват': 200 },
  { name: 'Месяц 1', 'Охват': 220 },
  { name: 'Месяц 2', 'Охват': 210 },
  { name: 'Месяц 3 (с Zenith)', 'Охват': 450 },
  { name: 'Месяц 4', 'Охват': 680 },
  { name: 'Месяц 5', 'Охват': 950 },
];

const cardVariants = {
    offscreen: { y: 50, opacity: 0 },
    onscreen: { y: 0, opacity: 1, transition: { type: "spring", bounce: 0.4, duration: 0.8 } }
};

const SectionWrapper = ({ children, background = 'transparent', py = { xs: 8, md: 12 } }) => (
    <Box sx={{ py, backgroundColor: background, overflow: 'hidden' }}>
        <Container maxWidth="lg">{children}</Container>
    </Box>
);

const FeatureCard = ({ icon, title, description }) => (
    <Stack spacing={2} direction="row" alignItems="flex-start">
        <Box sx={{ fontSize: '2.5rem', mt: 0.5, color: 'primary.main' }}>{icon}</Box>
        <Box>
            <Typography variant="h6" sx={{fontWeight: 600}}>{title}</Typography>
            <Typography color="text.secondary">{description}</Typography>
        </Box>
    </Stack>
);

export default function HomePage() {
  return (
    <Box>
      {/* Секция 1: Главный экран (Hero) */}
      <SectionWrapper py={{ xs: 12, md: 16 }}>
        <motion.div initial={{ opacity: 0, y: -30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
          <Typography 
            variant="h1" 
            component="h1" 
            gutterBottom 
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
          <Typography variant="h5" color="text.secondary" paragraph sx={{ mb: 4, maxWidth: '750px', mx: 'auto', textAlign: 'center' }}>
            Zenith — это ваш персональный ассистент для ВКонтакте, созданный для органического роста, повышения охватов и тотальной автоматизации рутины. Безопасно, эффективно, интеллектуально.
          </Typography>
          <Box sx={{ display: 'flex', justifyContent: 'center' }}>
            <Button variant="contained" size="large" component={RouterLink} to="/dashboard" sx={{py: 1.5, px: 5, fontSize: '1.1rem'}}>
                Начать бесплатно
            </Button>
          </Box>
        </motion.div>
      </SectionWrapper>

      {/* Секция 2: Ключевые преимущества */}
      <SectionWrapper background={(theme) => alpha(theme.palette.background.paper, 0.5)}>
          <Grid container spacing={5} alignItems="center">
              <Grid item xs={12} md={6}>
                  <motion.div initial={{ opacity: 0, x: -50 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true, amount: 0.5 }} transition={{ duration: 0.7 }}>
                     <Typography variant="h3" component="h2" sx={{ fontWeight: 700, mb: 2 }}>
                        Ваше стратегическое преимущество
                      </Typography>
                      <Typography variant="h6" color="text.secondary" paragraph sx={{ mb: 4 }}>
                          Мы объединили передовые технологии и глубокое понимание алгоритмов, чтобы вы получали измеримый результат.
                      </Typography>
                      <Stack spacing={4}>
                          <FeatureCard icon={<SecurityIcon />} title="Безопасность — наш приоритет" description="Система работает через временный токен VK, не запрашивая ваш пароль. Для максимальной анонимности реализована поддержка личных прокси-серверов."/>
                          <FeatureCard icon={<AutoAwesomeIcon />} title="Интеллектуальная имитация" description="Наш алгоритм Humanizer™ подбирает динамические интервалы между действиями, делая автоматизацию неотличимой от ручной работы."/>
                          <FeatureCard icon={<TimerIcon />} title="Автоматизация 24/7" description="Настройте расписание или сложные Сценарии один раз, и Zenith будет работать на вас круглосуточно, даже когда вы оффлайн."/>
                      </Stack>
                  </motion.div>
              </Grid>
              {/* Секция с графиком-проекцией */}
              <Grid item xs={12} md={6}>
                   <motion.div initial="offscreen" whileInView="onscreen" viewport={{ once: true, amount: 0.5 }} variants={cardVariants}>
                       <Paper sx={{ p: 3, height: 400, display: 'flex', flexDirection: 'column' }}>
                           <Typography variant="h6" sx={{ fontWeight: 600 }}>Проекция роста охватов</Typography>
                           <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>Пример влияния регулярной активности на видимость профиля.</Typography>
                           <ResponsiveContainer width="100%" height="100%">
                               <AreaChart data={projectionData} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
                                   <defs>
                                       <linearGradient id="colorUv" x1="0" y1="0" x2="0" y2="1">
                                           <stop offset="5%" stopColor="#5E5CE6" stopOpacity={0.8}/>
                                           <stop offset="95%" stopColor="#5E5CE6" stopOpacity={0}/>
                                       </linearGradient>
                                   </defs>
                                   <XAxis dataKey="name" stroke="#A0A3BD" fontSize="0.8rem" />
                                   <YAxis stroke="#A0A3BD" fontSize="0.8rem"/>
                                   <CartesianGrid strokeDasharray="3 3" stroke={alpha("#A0A3BD", 0.1)} />
                                   <Tooltip contentStyle={{ backgroundColor: '#17181D', border: '1px solid #A0A3BD25', borderRadius: '12px' }}/>
                                   <Area type="monotone" dataKey="Охват" stroke="#5E5CE6" fillOpacity={1} fill="url(#colorUv)" strokeWidth={3} />
                               </AreaChart>
                           </ResponsiveContainer>
                       </Paper>
                   </motion.div>
              </Grid>
          </Grid>
      </SectionWrapper>
      
      {/* Секция 3: Как это работает */}
       <SectionWrapper>
          <Typography variant="h3" component="h2" textAlign="center" gutterBottom sx={{ mb: 8, fontWeight: 700 }}>
              Всего 3 шага к результату
          </Typography>
          <Grid container spacing={4} alignItems="stretch">
              {[
                  { num: "1", title: "Безопасная авторизация", desc: "Получите временный ключ доступа VK. Мы никогда не запрашиваем и не храним ваш логин и пароль." },
                  { num: "2", title: "Гибкая настройка", desc: "Выберите действие, настройте мощные фильтры или создайте собственный сценарий работы по расписанию." },
                  { num: "3", title: "Анализ и контроль", desc: "Наблюдайте за выполнением каждой операции в реальном времени и отслеживайте рост вашего аккаунта." },
              ].map((step, i) => (
                  <Grid item xs={12} md={4} key={step.num}>
                       <motion.div initial="offscreen" whileInView="onscreen" viewport={{ once: true, amount: 0.5 }} transition={{ delay: i * 0.15 }} variants={cardVariants} style={{ textAlign: 'center', padding: '24px', height: '100%' }}>
                          <Typography variant="h1" color="primary.main" sx={{fontWeight: 800, opacity: 0.1}}>{step.num}</Typography>
                          <Typography variant="h5" sx={{mt: -5, mb: 1, fontWeight: 600}}>{step.title}</Typography>
                          <Typography color="text.secondary">{step.desc}</Typography>
                      </motion.div>
                  </Grid>
              ))}
          </Grid>
      </SectionWrapper>
      
      {/* Секция 4: Призыв к действию (CTA) */}
       <SectionWrapper>
        <Paper sx={{ p: {xs: 4, md: 8}, textAlign: 'center', backgroundImage: (theme) => `linear-gradient(45deg, ${theme.palette.primary.main} 30%, ${theme.palette.secondary.main} 90%)`, borderRadius: 4 }}>
            <motion.div initial="offscreen" whileInView="onscreen" viewport={{ once: true, amount: 0.5 }} variants={cardVariants}>
                <Typography variant="h3" component="h2" sx={{ fontWeight: 700, color: 'white' }}>Готовы начать трансформацию?</Typography>
                <Typography variant="h6" sx={{ my: 3, color: 'rgba(255,255,255,0.8)', maxWidth: '600px', mx: 'auto' }}>
                    Присоединяйтесь к Zenith сегодня и начните свой путь к эффективному SMM.
                </Typography>
                <Button variant="contained" size="large" component={RouterLink} to="/dashboard" sx={{ py: 1.5, px: 5, fontSize: '1.1rem', bgcolor: 'white', color: 'primary.main', '&:hover': { bgcolor: 'grey.200' }}}>
                    Попробовать бесплатно
                </Button>
            </motion.div>
        </Paper>
      </SectionWrapper>
    </Box>
  );
}