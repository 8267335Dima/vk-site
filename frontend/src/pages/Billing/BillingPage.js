// frontend/src/pages/Billing/BillingPage.js
import React, { useState, useMemo } from 'react';
import { Container, Typography, Grid, Paper, Button, Box, Chip, List, ListItem, ListItemIcon, Divider, CircularProgress, Skeleton, Switch, Stack } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import StarIcon from '@mui/icons-material/Star';
import { motion } from 'framer-motion';
import { useUserStore } from 'store/userStore';
import { pageHeader, planDetails as fallbackPlans } from 'content/billingPageContent'; // --- ИЗМЕНЕНИЕ: Импортируем обновленный контент
import { createPayment, fetchAvailablePlans } from 'api';
import { toast } from 'react-hot-toast';
import { useQuery } from '@tanstack/react-query';

const PlanCard = ({ plan, isCurrentPlan, onChoose, isLoadingPayment, isAnnual }) => {
    const price = isAnnual ? Math.round(plan.price * 12 * 0.8) : plan.price;
    const period = isAnnual ? '/ год' : '/ мес.';

    return (
        <Grid item xs={12} md={4}>
            {/* --- ИЗМЕНЕНИЕ: Улучшенная анимация --- */}
            <motion.div
                variants={{ hidden: { opacity: 0, y: 50 }, visible: { opacity: 1, y: 0 } }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                style={{ height: '100%' }}
            >
                <Paper
                  sx={{
                    p: 4, display: 'flex', flexDirection: 'column', height: '100%',
                    border: 2, borderColor: isCurrentPlan ? 'success.main' : (plan.isPopular ? 'primary.main' : 'transparent'),
                    position: 'relative', 
                    transform: plan.isPopular ? { xs: 'none', md: 'scale(1.05)' } : 'none',
                    zIndex: plan.isPopular ? 1 : 0, 
                    boxShadow: plan.isPopular ? '0 16px 48px -16px rgba(126, 87, 194, 0.3)' : 'inherit',
                  }}
                >
                    {plan.isPopular && <Chip icon={<StarIcon />} label="Рекомендуем" color="primary" size="small" sx={{ position: 'absolute', top: 16, right: 16 }} />}
                    <Typography variant="h5" component="h2" sx={{ fontWeight: 600 }}>{plan.display_name}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ minHeight: '40px', mt: 1 }}>{plan.description}</Typography>
                    
                    <Box sx={{ my: 3 }}>
                        <Typography variant="h3" component="p" sx={{ fontWeight: 700 }}>
                            {price > 0 ? price : "Бесплатно"}
                            {price > 0 && <Typography variant="h6" component="span" color="text.secondary"> ₽ {period}</Typography>}
                        </Typography>
                    </Box>
                    <Divider sx={{ my: 2 }} />

                    <Box sx={{ my: 2, flexGrow: 1 }}>
                        <List sx={{ p: 0 }}>
                            {plan.features?.map((feature, index) => (
                                <ListItem key={index} disablePadding sx={{ mb: 1.5 }}>
                                    <ListItemIcon sx={{ minWidth: '32px' }}><CheckIcon color={isCurrentPlan ? 'success' : 'primary'} fontSize="small"/></ListItemIcon>
                                    <Typography variant="body1">{feature}</Typography>
                                </ListItem>
                            ))}
                        </List>
                    </Box>
                    <Button
                        variant={isCurrentPlan ? 'outlined' : (plan.isPopular ? 'contained' : 'outlined')}
                        size="large" fullWidth
                        disabled={isCurrentPlan || isLoadingPayment || plan.price === 0}
                        onClick={() => onChoose(plan.id)}
                        sx={{ mt: 'auto', minHeight: 48 }}
                        color={isCurrentPlan ? 'success' : 'primary'}
                    >
                        {isLoadingPayment ? <CircularProgress size={24} color="inherit" /> : (isCurrentPlan ? "Ваш текущий план" : "Выбрать план")}
                    </Button>
                </Paper>
            </motion.div>
        </Grid>
    );
};

export default function BillingPage() {
    const userInfo = useUserStore((state) => state.userInfo);
    const currentUserPlanId = userInfo?.plan || 'Базовый';
    const [loadingPlan, setLoadingPlan] = useState(null);
    const [isAnnual, setIsAnnual] = useState(false);

    const { data: apiPlans, isLoading } = useQuery({
        queryKey: ['plans'],
        queryFn: fetchAvailablePlans,
        staleTime: 1000 * 60 * 60,
    });
    
    const plansToDisplay = useMemo(() => {
        const purchasablePlans = apiPlans?.plans || fallbackPlans.filter(p => p.price > 0);
        const basePlanInfo = fallbackPlans.find(p => p.id === 'Базовый');

        if (currentUserPlanId === 'Базовый' && basePlanInfo) {
            return [basePlanInfo, ...purchasablePlans];
        }
        
        return purchasablePlans;

    }, [apiPlans, currentUserPlanId]);


    const handleChoosePlan = async (planId) => {
        setLoadingPlan(planId);
        try {
            const response = await createPayment(planId);
            window.location.href = response.confirmation_url;
        } catch (error) {
            toast.error("Не удалось создать платеж. Пожалуйста, попробуйте позже.");
        } finally {
            setLoadingPlan(null);
        }
    };

    const containerVariants = {
        hidden: { opacity: 0 },
        // --- ИЗМЕНЕНИЕ: Улучшенная анимация для дочерних элементов ---
        visible: { opacity: 1, transition: { staggerChildren: 0.15, delayChildren: 0.2 } },
    };

    return (
        <Container maxWidth="lg" sx={{ mt: 4, py: 8 }}>
            <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
                <Typography variant="h3" component="h1" textAlign="center" gutterBottom sx={{fontWeight: 700}}>{pageHeader.title}</Typography>
                <Typography variant="h6" color="text.secondary" textAlign="center" sx={{ mb: 6, maxWidth: '700px', mx: 'auto' }}>{pageHeader.subtitle}</Typography>
                 <Stack direction="row" spacing={2} alignItems="center" justifyContent="center" sx={{mb: 10}}>
                    <Typography>Ежемесячно</Typography>
                    <Switch checked={isAnnual} onChange={(e) => setIsAnnual(e.target.checked)} />
                    <Typography>Ежегодно</Typography>
                    <Chip label="Скидка 20%" color="success" size="small"/>
                </Stack>
            </motion.div>
            
            <motion.div variants={containerVariants} initial="hidden" animate="visible">
                <Grid container spacing={{ xs: 3, md: 5 }} alignItems="stretch" justifyContent="center">
                    {isLoading && !apiPlans ? (
                        Array.from(new Array(3)).map((_, index) => (
                           <Grid item xs={12} md={4} key={index}> <Skeleton variant="rounded" height={500} /> </Grid>
                        ))
                    ) : (
                        plansToDisplay.map((plan) => (
                            <PlanCard
                                key={plan.id}
                                plan={plan}
                                isCurrentPlan={plan.id === currentUserPlanId && !(userInfo.plan_expires_at && new Date(userInfo.plan_expires_at) < new Date())}
                                onChoose={handleChoosePlan}
                                isLoadingPayment={loadingPlan === plan.id}
                                isAnnual={isAnnual}
                            />
                        ))
                    )}
                </Grid>
            </motion.div>
        </Container>
    );
}