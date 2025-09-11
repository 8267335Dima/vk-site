// frontend/src/pages/Home/HomePage.js
import React from 'react';
import { Box, alpha } from '@mui/material';

// Импортируем все секции страницы из новой папки components
import HeroSection from './components/HeroSection';
import FeaturesSection from './components/FeaturesSection';
import AdvantageSection from './components/AdvantageSection';
import StepsSection from './components/StepsSection';
import CtaSection from './components/CtaSection';

// Стилизованный компонент-обертка для всех секций, чтобы обеспечить единые отступы и фон
export const SectionWrapper = ({ children, background = 'transparent', py = { xs: 8, md: 12 } }) => (
    <Box sx={{ py, backgroundColor: background, overflow: 'hidden' }}>
        {children}
    </Box>
);

export default function HomePage() {
  return (
    <Box>
      <SectionWrapper py={{ xs: 12, md: 16 }}>
        <HeroSection />
      </SectionWrapper>

      <SectionWrapper background={(theme) => alpha(theme.palette.background.paper, 0.5)}>
        <FeaturesSection />
      </SectionWrapper>
      
      <SectionWrapper>
        <AdvantageSection />
      </SectionWrapper>
      
      <SectionWrapper background={(theme) => alpha(theme.palette.background.paper, 0.5)}>
        <StepsSection />
      </SectionWrapper>
      
      <SectionWrapper>
        <CtaSection />
      </SectionWrapper>
    </Box>
  );
}