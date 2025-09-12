// frontend/src/pages/Billing/BillingPage.js
import React, { useState, useMemo } from 'react';
import { Container, Typography, Grid, Paper, Button, Box, Chip, List, ListItem, ListItemIcon, Divider, CircularProgress, Skeleton, Switch, Stack, alpha } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import StarIcon from '@mui/icons-material/Star';
import { motion } from 'framer-motion';
import { useUserStore } from 'store/userStore';
import { createPayment, fetchAvailablePlans } from 'api.js';
import { toast } from 'react-hot-toast';
import { useQuery } from '@tanstack/react-query';

const PlanCard = ({ plan, isCurrent, onChoose, isLoading, isAnnual }) => {
    const periodMonths = isAnnual ? 12 : 1;
    const periodInfo = plan.periods?.find(p => p.months === periodMonths);
    
    const finalPrice = useMemo(() => {
        if (plan.price === 0) return 0;
        let price = plan.price * periodMonths;
        if (isAnnual && periodInfo) {
            price *= (1 - periodInfo.discount_percent / 100);
        }
        return Math.round(price);
    }, [plan, isAnnual, periodMonths, periodInfo]);

    const pricePerMonth = finalPrice > 0 ? Math.round(finalPrice / periodMonths) : 0;
    const periodLabel = isAnnual ? '/ год' : '/ мес.';

    return (
        <Grid item xs={12} md={4}>
            <motion.div
                variants={{ hidden: { opacity: 0, y: 50 }, visible: { opacity: 1, y: 0 } }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                style={{ height: '100%' }}>
                <Paper
                  sx={{
                    p: 4, display: 'flex', flexDirection: 'column', height: '100%',
                    border: 2, borderColor: isCurrent ? 'success.main' : (plan.is_popular ? 'primary.main' : 'transparent'),
                    position: 'relative', 
                    transform: plan.is_popular ? { xs: 'none', md: 'scale(1.05)' } : 'none',
                    zIndex: plan.is_popular ? 1 : 0, 
                    boxShadow: plan.is_popular ? (theme) => `0 16px 48px -16px ${alpha(theme.palette.primary.main, 0.3)}` : 'inherit',
                  }}>
                    {plan.is_popular && <Chip icon={<StarIcon />} label="Рекомендуем" color="primary" size="small" sx={{ position: 'absolute', top: 16, right: 16 }} />}
                    <Typography variant="h5" component="h2" sx={{ fontWeight: 700 }}>{plan.display_name}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ minHeight: '40px', mt: 1 }}>{plan.description}</Typography>
                    <Box sx={{ my: 3, display: 'flex', alignItems: 'flex-end', gap: 1 }}>
                        <Typography variant="h3" component="p" sx={{ fontWeight: 700, lineHeight: 1 }}>
                            {finalPrice > 0 ? finalPrice : "Бесплатно"}
                        </Typography>
                         {finalPrice > 0 && <Typography variant="h6" component="span" color="text.secondary">₽ {periodLabel}</Typography>}
                    </Box>
                    {isAnnual && plan.price > 0 && <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{pricePerMonth} ₽ / мес.</Typography>}
                    <Divider sx={{ my: 2 }} />
                    <Box sx={{ my: 2, flexGrow: 1 }}>
                        <List sx={{ p: 0 }}>
                            {plan.features?.map((feature, index) => (
                                <ListItem key={index} disablePadding sx={{ mb: 1.5 }}>
                                    <ListItemIcon sx={{ minWidth: '32px' }}><CheckIcon color={isCurrent ? 'success' : 'primary'} fontSize="small"/></ListItemIcon>
                                    <Typography variant="body1">{feature}</Typography>
                                </ListItem>
                            ))}
                        </List>
                    </Box>
                    <Button
                        variant={isCurrent ? 'outlined' : (plan.is_popular ? 'contained' : 'outlined')}
                        size="large" fullWidth disabled={isCurrent || isLoading || plan.price === 0}
                        onClick={() => onChoose(plan.id, periodMonths)}
                        sx={{ mt: 'auto', minHeight: 48 }} color={isCurrent ? 'success' : 'primary'}>
                        {isLoading ? <CircularProgress size={24} color="inherit" /> : (isCurrent ? "Ваш текущий план" : "Выбрать план")}
                    </Button>
                </Paper>
            </motion.div>
        </Grid>
    );
};

export default function BillingPage() {
    const userInfo = useUserStore((state) => state.userInfo);
    const [loadingPlan, setLoadingPlan] = useState(null);
    const [isAnnual, setIsAnnual] = useState(false);

    const { data: plansData, isLoading } = useQuery({ queryKey: ['plans'], queryFn: fetchAvailablePlans });
    
    const handleChoosePlan = async (planId, months) => {
        setLoadingPlan(planId);
        try {
            const response = await createPayment(planId, months);
            window.location.href = response.confirmation_url;
        } catch (error) {
            toast.error("Не удалось создать платеж. Пожалуйста, попробуйте позже.");
        } finally {
            setLoadingPlan(null);
        }
    };

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: { opacity: 1, transition: { staggerChildren: 0.15, delayChildren: 0.2 } },
    };

    return (
        <Container maxWidth="lg" sx={{ py: { xs: 4, md: 8 } }}>
            <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
                <Typography variant="h3" component="h1" textAlign="center" gutterBottom sx={{fontWeight: 700}}>Выберите свой путь к успеху</Typography>
                <Typography variant="h6" color="text.secondary" textAlign="center" sx={{ mb: 6, maxWidth: '700px', mx: 'auto' }}>Выберите план, который идеально подходит для ваших целей и откроет новые горизонты для вашего профиля.</Typography>
                 <Stack direction="row" spacing={2} alignItems="center" justifyContent="center" sx={{mb: 8}}>
                    <Typography fontWeight={isAnnual ? 400 : 600} color={isAnnual ? 'text.secondary' : 'text.primary'}>Ежемесячно</Typography>
                    <Switch checked={isAnnual} onChange={(e) => setIsAnnual(e.target.checked)} />
                    <Typography fontWeight={isAnnual ? 600 : 400} color={isAnnual ? 'text.primary' : 'text.secondary'}>Ежегодно</Typography>
                    <Chip label="Выгода до 30%" color="success" size="small" variant="outlined"/>
                </Stack>
            </motion.div>
            
            <motion.div variants={containerVariants} initial="hidden" animate="visible">
                <Grid container spacing={{ xs: 3, md: 5 }} alignItems="stretch" justifyContent="center">
                    {isLoading ? (
                        Array.from(new Array(3)).map((_, index) => (
                           <Grid item xs={12} md={4} key={index}> <Skeleton variant="rounded" height={550} sx={{ borderRadius: 4 }} /> </Grid>
                        ))
                    ) : (
                        plansData?.plans.map((plan) => (
                            <PlanCard
                                key={plan.id} plan={plan}
                                isCurrent={plan.id === userInfo?.plan && userInfo?.is_plan_active}
                                onChoose={handleChoosePlan} isLoading={loadingPlan === plan.id}
                                isAnnual={isAnnual}
                            />
                        ))
                    )}
                </Grid>
            </motion.div>
        </Container>
    );
}