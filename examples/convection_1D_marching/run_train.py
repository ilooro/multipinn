import os

import hydra
from hydra.utils import instantiate
from omegaconf import DictConfig

from examples.convection_1D_marching.problem import convection_problem
from multipinn import *
from multipinn.utils import (
    initialize_model,
    initialize_regularization,
    save_config,
    set_device_and_seed,
)


@hydra.main(config_path="configs", config_name="config", version_base=None)
def train(cfg: DictConfig):
    config_save_path = os.path.join(cfg.paths.save_dir, "used_config.yaml")
    save_config(cfg, config_save_path)

    conditions, input_dim, output_dim, divide = convection_problem(
        cfg.problem.betta, cfg.problem.t_max
    )

    set_device_and_seed(cfg.trainer.random_seed)

    model = initialize_model(cfg, input_dim, output_dim)
    calc_loss = initialize_regularization(cfg)

    type_gen = "pseudo"

    generator_bound = Generator(cfg.generator.bound_points, type_gen)
    generator_domain = Generator(cfg.generator.domain_points, type_gen)

    generator_bound.use_for(conditions)
    generator_domain.use_for(conditions[0])

    pinn = PINN(model=model, conditions=conditions)

    optimizer = instantiate(cfg.optimizer, params=model.parameters())

    scheduler = instantiate(cfg.scheduler, optimizer=optimizer)

    grid = heatmap.Grid.from_pinn(pinn, cfg.visualization.grid_plot_points)

    callbacks = [
        progress.TqdmBar(
            "Epoch {epoch} lr={lr:.2e} Loss={loss_eq} Total={total_loss:.2e}"
        ),
        curve.LossCurve(cfg.paths.save_dir, cfg.visualization.save_period),
        save.SaveModel(cfg.paths.save_dir, period=cfg.visualization.save_period),
        heatmap.HeatmapPredictionMarching(
            grid=grid,
            save_dir=cfg.paths.save_dir,
            save_mode=cfg.visualization.save_mode,
            epochs_per_iter=cfg.model.marching.epochs_per_iter,
        ),
    ]

    callbacks += [
        points.LiveScatterPrediction(
            save_dir=cfg.paths.save_dir,
            period=cfg.visualization.save_period,
            save_mode=cfg.visualization.save_mode,
            output_index=0,
        )
    ]

    trainer = Trainer(
        pinn=pinn,
        optimizer=optimizer,
        scheduler=scheduler,
        num_epochs=cfg.trainer.num_epochs,
        update_grid_every=cfg.trainer.grid_update,
        calc_loss=calc_loss,
        callbacks_organizer=CallbacksOrganizer(callbacks),
    )

    marching_trainer = MarchingTrainer(
        steps=cfg.model.marching.steps,
        trainer=trainer,
        epochs_per_iter=cfg.model.marching.epochs_per_iter,
        divide=divide,
    )
    marching_trainer.march_trainer()


if __name__ == "__main__":
    train()
