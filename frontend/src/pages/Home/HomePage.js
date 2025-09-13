// frontend/src/pages/Home/HomePage.js
import React from 'react';
import { Box, alpha, Container } from '@mui/material';
import HeroSection from './components/HeroSection';
import FeaturesSection from './components/FeaturesSection';
import AdvantageSection from './components/AdvantageSection';
import StepsSection from './components/StepsSection';
import CtaSection from './components/CtaSection';
import CaseStudiesSection from './components/CaseStudiesSection';
import PrinciplesSection from './components/PrinciplesSection';
import FaqSection from './components/FaqSection';

export const SectionWrapper = ({ children, background = 'transparent', py = { xs: 8, md: 12 } }) => (
    <Box sx={{ py, backgroundColor: background, overflow: 'hidden' }}>
        <Container maxWidth="lg">
            {children}
        </Container>
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
        <CaseStudiesSection />
      </SectionWrapper>
      
      <SectionWrapper>
        <StepsSection />
      </SectionWrapper>
      
      <SectionWrapper background={(theme) => alpha(theme.palette.background.paper, 0.5)}>
        <PrinciplesSection />
      </SectionWrapper>
      
      <SectionWrapper>
        <FaqSection />
      </SectionWrapper>
      
      <SectionWrapper>
        <CtaSection />
      </SectionWrapper>
    </Box>
  );
}