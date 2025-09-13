// --- frontend/src/pages/Billing/components/PlanCard.js ---
import React from 'react';
import { Paper, Button, Box, Chip, List, ListItem, ListItemIcon, Divider, CircularProgress, Typography, Stack, alpha } from '@mui/material';
import CheckIcon from '@mui/icons-material/Check';
import StarIcon from '@mui/icons-material/Star';
import AutoAwesomeOutlinedIcon from '@mui/icons-material/AutoAwesomeOutlined';
import RocketLaunchOutlinedIcon from '@mui/icons-material/RocketLaunchOutlined';
import DiamondOutlinedIcon from '@mui/icons-material/DiamondOutlined';

const PlanCard = ({ plan, isCurrent, onChoose, isLoading, selectedMonths, periodInfo }) => {

    const originalPrice = plan.price * selectedMonths;
    const finalPrice = plan.price === 0 ? 0 : Math.round(originalPrice * (1 - (periodInfo?.discount_percent || 0) / 100));
    const pricePerMonth = finalPrice > 0 ? Math.round(finalPrice / selectedMonths) : 0;

    const planMeta = {
        "Базовый": { icon: <AutoAwesomeOutlinedIcon />, color: 'info' },
        "Plus": { icon: <RocketLaunchOutlinedIcon />, color: 'primary' },
        "PRO": { icon: <DiamondOutlinedIcon />, color: 'secondary' }
    };
    const meta = planMeta[plan.display_name] || { icon: <StarIcon />, color: 'primary' };

    return (
        <Paper
          sx={{
            p: 4, display: 'flex', flexDirection: 'column', height: '100%',
            position: 'relative', overflow: 'hidden',
            boxShadow: plan.is_popular ? (theme) => `0 16px 48px -16px ${alpha(theme.palette[meta.color].main, 0.4)}` : 'inherit',
            '&:before': {
                content: '""', position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                borderRadius: 'inherit', padding: '2px',
                background: isCurrent ? (t) => `linear-gradient(45deg, ${t.palette.success.main}, ${t.palette.success.dark})`
                          : plan.is_popular ? (t) => `linear-gradient(45deg, ${t.palette[meta.color].main}, ${t.palette[meta.color].dark})`
                          : 'transparent',
                WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
                WebkitMaskComposite: 'xor', maskComposite: 'exclude', pointerEvents: 'none',
            },
          }}>
            {plan.is_popular && <Chip icon={<StarIcon />} label="Рекомендуем" color={meta.color} size="small" sx={{ position: 'absolute', top: 16, right: 16 }} />}
            
            <Stack direction="row" spacing={2} alignItems="center" sx={{mb: 2}}>
                <Box sx={{ color: `${meta.color}.main`, fontSize: '2.5rem' }}>{meta.icon}</Box>
                <Typography variant="h5" component="h2" sx={{ fontWeight: 700 }}>{plan.display_name}</Typography>
            </Stack>
            
            <Typography variant="body2" color="text.secondary" sx={{ minHeight: '40px' }}>{plan.description}</Typography>
            
            <Box sx={{ my: 3, display: 'flex', alignItems: 'flex-end', gap: 1 }}>
                <Typography variant="h3" component="p" sx={{ fontWeight: 700, lineHeight: 1 }}>
                    {finalPrice > 0 ? finalPrice.toLocaleString('ru-RU') : "Бесплатно"}
                </Typography>
                 {finalPrice > 0 && <Typography variant="h6" component="span" color="text.secondary">₽</Typography>}
            </Box>
            
            <Stack direction="row" spacing={1} alignItems="center" sx={{minHeight: 40}}>
                 {periodInfo?.discount_percent > 0 && (
                     <>
                        <Typography variant="body2" color="text.secondary" sx={{ textDecoration: 'line-through' }}>
                            {originalPrice.toLocaleString('ru-RU')} ₽
                        </Typography>
                        <Chip label={`Выгода ${periodInfo.discount_percent}%`} color="success" variant="outlined" size="small" sx={{ fontWeight: 600 }} />
                     </>
                 )}
                 {selectedMonths > 1 && plan.price > 0 && <Chip label={`~${pricePerMonth.toLocaleString('ru-RU')} ₽ / мес.`} size="small" />}
            </Stack>
            
            <Divider sx={{ my: 2 }} />
            <Box sx={{ my: 2, flexGrow: 1 }}>
                <List sx={{ p: 0 }}>
                    {plan.features?.map((feature, index) => (
                        <ListItem key={index} disablePadding sx={{ mb: 1.5 }}>
                            <ListItemIcon sx={{ minWidth: '32px' }}><CheckIcon color={isCurrent ? 'success' : meta.color} fontSize="small"/></ListItemIcon>
                            <Typography variant="body1">{feature}</Typography>
                        </ListItem>
                    ))}
                </List>
            </Box>
            <Button
                variant={isCurrent ? 'outlined' : (plan.is_popular ? 'contained' : 'outlined')}
                size="large" fullWidth disabled={isCurrent || isLoading || plan.price === 0}
                onClick={() => onChoose(plan.id)}
                sx={{ mt: 'auto', minHeight: 48 }} color={isCurrent ? 'success' : meta.color}>
                {isLoading ? <CircularProgress size={24} color="inherit" /> : (isCurrent ? "Ваш текущий план" : "Выбрать")}
            </Button>
        </Paper>
    );
};

export default PlanCard;