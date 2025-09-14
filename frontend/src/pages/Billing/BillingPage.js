import React, { useState } from 'react';
import {
  Container,
  Typography,
  Grid,
  Skeleton,
  Stack,
  ToggleButtonGroup,
  ToggleButton,
  Box,
  Paper,
  alpha,
} from '@mui/material';
import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'react-hot-toast';

// УЛУЧШЕНИЕ: Заменяем отсутствующую иконку SiMir на надежную RiBankCardFill
import { FaCcVisa, FaCcMastercard } from 'react-icons/fa';
import { RiBankCardFill } from 'react-icons/ri'; // <-- ИЗМЕНЕНИЕ ЗДЕСЬ

import { useCurrentUser } from '@/shared/lib/hooks/useCurrentUser';
import { createPayment, fetchAvailablePlans } from '@/shared/api';
import PlanCard from './components/PlanCard';

const periodOptions = [
  { months: 1, label: '1 месяц' },
  { months: 3, label: '3 месяца' },
  { months: 6, label: '6 месяцев' },
  { months: 12, label: '1 год' },
];

export default function BillingPage() {
  const { data: userInfo } = useCurrentUser();
  const [loadingPlan, setLoadingPlan] = useState(null);
  const [selectedMonths, setSelectedMonths] = useState(1);

  const { data: plansData, isLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: fetchAvailablePlans,
  });

  const handleChoosePlan = async (planId) => {
    setLoadingPlan(planId);
    try {
      const response = await createPayment(planId, selectedMonths);
      window.location.href = response.confirmation_url;
    } catch (error) {
      toast.error('Не удалось создать платеж. Пожалуйста, попробуйте позже.');
    } finally {
      setLoadingPlan(null);
    }
  };

  const handlePeriodChange = (event, newPeriod) => {
    if (newPeriod !== null) {
      setSelectedMonths(newPeriod);
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.1 } },
  };
  const itemVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: { opacity: 1, y: 0 },
  };

  return (
    <Box sx={{ position: 'relative', overflow: 'hidden' }}>
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: (theme) =>
            `radial-gradient(ellipse at 50% 0%, ${alpha(
              theme.palette.primary.dark,
              0.2
            )} 0%, transparent 70%)`,
          zIndex: 0,
        }}
      />
      <Container
        maxWidth="lg"
        sx={{ py: { xs: 4, md: 8 }, position: 'relative', zIndex: 1 }}
      >
        <motion.div
          initial="hidden"
          animate="visible"
          variants={containerVariants}
        >
          <motion.div variants={itemVariants}>
            <Typography
              variant="h3"
              component="h1"
              textAlign="center"
              gutterBottom
              sx={{ fontWeight: 700 }}
            >
              Прозрачные тарифы для вашего роста
            </Typography>
          </motion.div>
          <motion.div variants={itemVariants}>
            <Typography
              variant="h6"
              color="text.secondary"
              textAlign="center"
              sx={{ mb: 6, maxWidth: '700px', mx: 'auto' }}
            >
              Инвестируйте в автоматизацию, чтобы сосредоточиться на том, что
              действительно важно — на создании контента и живом общении.
            </Typography>
          </motion.div>

          <motion.div variants={itemVariants}>
            <Stack alignItems="center" sx={{ mb: 8 }}>
              <ToggleButtonGroup
                value={selectedMonths}
                exclusive
                onChange={handlePeriodChange}
                aria-label="billing period"
              >
                {periodOptions.map((opt) => (
                  <ToggleButton
                    key={opt.months}
                    value={opt.months}
                    sx={{ px: 3, py: 1 }}
                  >
                    {opt.label}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Stack>
          </motion.div>
        </motion.div>

        <Grid
          container
          spacing={{ xs: 3, md: 4 }}
          alignItems="stretch"
          justifyContent="center"
        >
          {isLoading
            ? Array.from(new Array(3)).map((_, index) => (
                <Grid item xs={12} md={4} key={index}>
                  <Skeleton
                    variant="rounded"
                    height={600}
                    sx={{ borderRadius: 4 }}
                  />
                </Grid>
              ))
            : plansData?.plans.map((plan) => (
                <Grid
                  item
                  xs={12}
                  md={4}
                  key={plan.id}
                  component={motion.div}
                  variants={itemVariants}
                  sx={{
                    zIndex: plan.is_popular ? 2 : 1,
                    transform: plan.is_popular
                      ? { xs: 'none', md: 'scale(1.05)' }
                      : 'none',
                  }}
                >
                  <PlanCard
                    plan={plan}
                    isCurrent={
                      plan.id === userInfo?.plan && userInfo?.is_plan_active
                    }
                    onChoose={() => handleChoosePlan(plan.id)}
                    isLoading={loadingPlan === plan.id}
                    selectedMonths={selectedMonths}
                    periodInfo={plan.periods?.find(
                      (p) => p.months === selectedMonths
                    )}
                  />
                </Grid>
              ))}
        </Grid>
        <motion.div variants={itemVariants}>
          <Paper
            variant="outlined"
            sx={{
              mt: 8,
              p: 3,
              maxWidth: 'sm',
              mx: 'auto',
              bgcolor: 'transparent',
            }}
          >
            <Stack
              direction="row"
              spacing={3}
              justifyContent="center"
              alignItems="center"
            >
              <Typography variant="body2" color="text.secondary">
                Безопасная оплата:
              </Typography>
              <Stack
                direction="row"
                spacing={2}
                alignItems="center"
                sx={{ color: 'text.secondary', fontSize: '28px' }}
              >
                <FaCcVisa />
                <FaCcMastercard />
                {/* ИСПРАВЛЕНИЕ: Используем новую иконку */}
                <RiBankCardFill title="МИР" />
              </Stack>
            </Stack>
          </Paper>
        </motion.div>
      </Container>
    </Box>
  );
}
