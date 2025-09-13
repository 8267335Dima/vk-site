// frontend/src/pages/Home/components/FaqSection.js
import React from 'react';
import { Typography, Accordion, AccordionSummary, AccordionDetails, Box, alpha, Icon } from '@mui/material';
import { motion } from 'framer-motion';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SecurityOutlinedIcon from '@mui/icons-material/SecurityOutlined';
import ComputerOutlinedIcon from '@mui/icons-material/ComputerOutlined';
import AccountTreeOutlinedIcon from '@mui/icons-material/AccountTreeOutlined';
import VpnKeyOutlinedIcon from '@mui/icons-material/VpnKeyOutlined';
import EventBusyOutlinedIcon from '@mui/icons-material/EventBusyOutlined';

const faqData = [
    { icon: <SecurityOutlinedIcon />, q: 'Насколько безопасно использовать Zenith?', a: 'Абсолютно. Мы используем временный ключ доступа (токен) Kate Mobile, который не дает доступа к вашим личным данным, паролю или сообщениям. К тому же, наш алгоритм Humanizer™ имитирует действия реального человека, сводя риски блокировки к минимуму.' },
    { icon: <ComputerOutlinedIcon />, q: 'Нужно ли мне держать компьютер включенным?', a: 'Нет. Все задачи выполняются на наших защищенных облачных серверах. Вы можете настроить автоматизацию или сценарий, закрыть браузер и заниматься своими делами. Zenith будет работать на вас 24/7.' },
    { icon: <AccountTreeOutlinedIcon />, q: 'Что такое "сценарии" и чем они отличаются от автоматизации?', a: 'Автоматизация — это регулярное выполнение одного конкретного действия (например, авто-прием заявок). Сценарии — это мощный конструктор, где вы можете выстроить целую цепочку из разных действий, которые будут выполняться последовательно по заданному вами расписанию.' },
    { icon: <VpnKeyOutlinedIcon />, q: 'Могу ли я использовать свой прокси-сервер?', a: 'Да, на тарифе PRO вы получаете доступ к менеджеру прокси, где можете добавить, проверить и использовать собственные прокси-серверы для максимальной анонимности и обхода ограничений.' },
    { icon: <EventBusyOutlinedIcon />, q: 'Что произойдет после окончания бесплатного периода?', a: 'После 14-дневного базового периода ваш аккаунт будет переведен на ограниченный тариф "Expired". Все ваши настройки сохранятся, и вы сможете в любой момент выбрать платный тариф, чтобы продолжить использовать все возможности платформы.' },
];

const fadeInUp = {
    initial: { y: 40, opacity: 0 },
    animate: { y: 0, opacity: 1, transition: { type: "spring", stiffness: 100, damping: 20, duration: 0.8 } }
};
const staggerContainer = {
    animate: { transition: { staggerChildren: 0.1 } }
};

const FaqSection = () => {
    return (
        <Box>
            <motion.div initial="initial" whileInView="animate" variants={fadeInUp} viewport={{ once: true, amount: 0.5 }}>
                 <Typography variant="h3" component="h2" textAlign="center" sx={{ mb: 2, fontWeight: 700 }}>
                    Остались вопросы?
                </Typography>
                <Typography variant="h6" color="text.secondary" textAlign="center" sx={{ mb: 8, maxWidth: '700px', mx: 'auto' }}>
                    Мы собрали ответы на самые популярные из них, чтобы вы могли начать работу без сомнений.
                </Typography>
            </motion.div>
            <motion.div initial="initial" whileInView="animate" variants={staggerContainer} viewport={{ once: true, amount: 0.2 }}>
                <Box maxWidth="md" mx="auto">
                    {faqData.map((faq, i) => (
                        <motion.div variants={fadeInUp} key={i}>
                            <Accordion sx={{
                                mb: 1.5,
                                backgroundImage: 'none',
                                bgcolor: 'background.paper',
                                border: '1px solid',
                                borderColor: 'divider',
                                '&:before': { display: 'none' },
                                '&.Mui-expanded': { 
                                    margin: '0 0 12px 0',
                                    borderColor: 'primary.main',
                                    boxShadow: (theme) => `0 8px 24px ${alpha(theme.palette.primary.main, 0.1)}`,
                                },
                            }}>
                                <AccordionSummary 
                                  expandIcon={<ExpandMoreIcon />}
                                  sx={{ minHeight: 72, '& .MuiAccordionSummary-content': { alignItems: 'center', gap: 2 } }}
                                >
                                    <Icon sx={{ color: 'primary.main' }}>{faq.icon}</Icon>
                                    <Typography variant="h6" sx={{fontWeight: 600}}>{faq.q}</Typography>
                                </AccordionSummary>
                                <AccordionDetails sx={{ pt: 0, pb: 2, px: 3 }}>
                                    <Typography color="text.secondary">{faq.a}</Typography>
                                </AccordionDetails>
                            </Accordion>
                        </motion.div>
                    ))}
                </Box>
            </motion.div>
        </Box>
    );
};

export default FaqSection;