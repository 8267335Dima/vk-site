// frontend/src/pages/Scenarios/ScenarioPage.js
import React, { useState } from 'react';
import {
    Container, Typography, Box, Button, CircularProgress,
    Paper, Stack, IconButton, Chip, Tooltip, Switch, alpha
} from '@mui/material';
import AddCircleOutlineIcon from '@mui/icons-material/AddCircleOutline';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import PauseCircleOutlineIcon from '@mui/icons-material/PauseCircleOutline';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchScenarios, deleteScenario, updateScenario } from 'api';
import { toast } from 'react-hot-toast';
import cronstrue from 'cronstrue/i18n';
import ScenarioEditorModal from './ScenarioEditorModal';

const ScenarioCard = ({ scenario, onEdit, onDelete, onToggle }) => {
    const toggleMutation = useMutation({
        mutationFn: updateScenario,
        onSuccess: onToggle.onSuccess,
        onError: onToggle.onError,
    });

    const handleToggle = (event) => {
        const isActive = event.target.checked;
        toggleMutation.mutate({ ...scenario, is_active: isActive });
    };

    const isMutating = toggleMutation.isLoading;

    return (
        <Paper sx={{ p: 2.5, display: 'flex', alignItems: 'center', gap: 2, transition: 'box-shadow 0.2s', '&:hover': { boxShadow: 3 } }}>
            <Box sx={{ flexGrow: 1 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>{scenario.name}</Typography>
                <Typography variant="body2" color="text.secondary">
                    {cronstrue.toString(scenario.schedule, { locale: "ru" })}
                </Typography>
                <Stack direction="row" spacing={1} sx={{ mt: 1.5, flexWrap: 'wrap', gap: 1 }}>
                    {scenario.steps.slice(0, 5).map(step => (
                        <Chip key={step.id} label={step.action_type} size="small" variant="outlined" />
                    ))}
                    {scenario.steps.length > 5 && <Chip label={`+${scenario.steps.length - 5}`} size="small" />}
                </Stack>
            </Box>
            <Stack direction="row" alignItems="center" spacing={0.5}>
                <Tooltip title={scenario.is_active ? "Приостановить" : "Запустить"}>
                    <span>
                        <Switch
                            checked={scenario.is_active}
                            onChange={handleToggle}
                            disabled={isMutating}
                            icon={<PlayCircleOutlineIcon />}
                            checkedIcon={<PauseCircleOutlineIcon />}
                            color="success"
                        />
                    </span>
                </Tooltip>
                <IconButton onClick={() => onEdit(scenario)} disabled={isMutating}><EditIcon /></IconButton>
                <IconButton onClick={() => onDelete(scenario.id)} disabled={isMutating}><DeleteIcon sx={{color: 'error.light'}} /></IconButton>
            </Stack>
        </Paper>
    );
};

export default function ScenariosPage() {
    const queryClient = useQueryClient();
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingScenario, setEditingScenario] = useState(null);

    const { data: scenarios, isLoading } = useQuery({ queryKey: ['scenarios'], queryFn: fetchScenarios });

    const deleteMutation = useMutation({
        mutationFn: deleteScenario,
        onSuccess: () => {
            toast.success("Сценарий удален.");
            queryClient.invalidateQueries({ queryKey: ['scenarios'] });
        },
        onError: (error) => toast.error(error.message || "Ошибка удаления"),
    });
    
    const onToggleSuccess = () => {
        queryClient.invalidateQueries({ queryKey: ['scenarios'] });
        toast.success("Статус сценария обновлен.");
    };

    const handleOpenModal = (scenario = null) => {
        setEditingScenario(scenario);
        setIsModalOpen(true);
    };

    const handleCloseModal = () => {
        setEditingScenario(null);
        setIsModalOpen(false);
    };

    return (
        <>
            <Container maxWidth="md" sx={{ py: 4 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
                    <Typography variant="h4" component="h1" sx={{ fontWeight: 600 }}>
                        Мои Сценарии
                    </Typography>
                    <Button
                        variant="contained"
                        startIcon={<AddCircleOutlineIcon />}
                        onClick={() => handleOpenModal()}
                    >
                        Создать сценарий
                    </Button>
                </Box>

                {isLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}><CircularProgress /></Box>
                ) : (
                    <Stack spacing={2}>
                        {scenarios?.length === 0 ? (
                             <Paper sx={{ p: 5, textAlign: 'center', backgroundColor: (theme) => alpha(theme.palette.primary.main, 0.05) }}>
                                <Typography variant="h6" gutterBottom>У вас пока нет ни одного сценария</Typography>
                                <Typography color="text.secondary">Сценарии позволяют автоматически выполнять цепочки действий по заданному расписанию. Нажмите "Создать", чтобы добавить первый.</Typography>
                            </Paper>
                        ) : (
                            scenarios?.map(scenario => (
                                <ScenarioCard
                                    key={scenario.id}
                                    scenario={scenario}
                                    onEdit={handleOpenModal}
                                    onDelete={deleteMutation.mutate}
                                    onToggle={{ onSuccess: onToggleSuccess, onError: (error) => toast.error(error.message) }}
                                />
                            ))
                        )}
                    </Stack>
                )}
            </Container>
            <ScenarioEditorModal
                open={isModalOpen}
                onClose={handleCloseModal}
                scenario={editingScenario}
            />
        </>
    );
}