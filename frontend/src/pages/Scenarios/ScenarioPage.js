// --- frontend/src/pages/Scenarios/ScenarioPage.js ---
import React from 'react';
import {
    Container, Typography, Box, Button, CircularProgress,
    Paper, Stack, IconButton, Switch, alpha, Grid
} from '@mui/material';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchScenarios, deleteScenario } from 'api';
import { toast } from 'react-hot-toast';
import cronstrue from 'cronstrue/i18n';
import { useNavigate } from 'react-router-dom';

const ScenarioCard = ({ scenario, onEdit, onDelete }) => {
    // В будущем здесь можно будет рендерить мини-карту сценария
    return (
        <Paper sx={{ p: 2.5, display: 'flex', flexDirection: 'column', height: '100%', transition: 'box-shadow 0.2s', '&:hover': { boxShadow: 3 } }}>
            <Box sx={{ flexGrow: 1 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>{scenario.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                    {cronstrue.toString(scenario.schedule, { locale: "ru" })}
                </Typography>
            </Box>
            <Stack direction="row" alignItems="center" spacing={0.5} sx={{ mt: 2 }}>
                <Switch checked={scenario.is_active} />
                <Box sx={{ flexGrow: 1 }} />
                <IconButton onClick={() => onEdit(scenario.id)}><EditIcon /></IconButton>
                <IconButton onClick={() => onDelete(scenario.id)}><DeleteIcon sx={{color: 'error.light'}} /></IconButton>
            </Stack>
        </Paper>
    );
};

export default function ScenariosPage() {
    const queryClient = useQueryClient();
    const navigate = useNavigate();
    const { data: scenarios, isLoading } = useQuery({ queryKey: ['scenarios'], queryFn: fetchScenarios });

    const deleteMutation = useMutation({
        mutationFn: deleteScenario,
        onSuccess: () => {
            toast.success("Сценарий удален.");
            queryClient.invalidateQueries({ queryKey: ['scenarios'] });
        },
        onError: (error) => toast.error(error.message || "Ошибка удаления"),
    });

    const handleCreate = () => navigate('/scenarios/new');
    const handleEdit = (id) => navigate(`/scenarios/${id}`);

    return (
        <Container maxWidth="lg" sx={{ py: 4 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
                    Мои Сценарии
                </Typography>
                <Button variant="contained" startIcon={<AddCircleOutlineIcon />} onClick={handleCreate}>
                    Создать сценарий
                </Button>
            </Box>

            {isLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
            ) : (
                <>
                    {scenarios?.length === 0 ? (
                        <Paper sx={{ p: 5, textAlign: 'center', backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.05), borderStyle: 'dashed' }}>
                            <Typography variant="h6" gutterBottom>У вас пока нет ни одного сценария</Typography>
                            <Typography color="text.secondary">Сценарии позволяют создавать сложные цепочки действий с условиями. Нажмите "Создать", чтобы построить свой первый автоматизированный воркфлоу.</Typography>
                        </Paper>
                    ) : (
                        <Grid container spacing={3}>
                            {scenarios?.map(scenario => (
                                <Grid item xs={12} sm={6} md={4} key={scenario.id}>
                                    <ScenarioCard
                                        scenario={scenario}
                                        onEdit={handleEdit}
                                        onDelete={deleteMutation.mutate}
                                    />
                                </Grid>
                            ))}
                        </Grid>
                    )}
                </>
            )}
        </Container>
    );
}