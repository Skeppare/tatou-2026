# Marcus – Operational Security

Threat modeling, logging and monitoring for the Tatou deployment.

## Files

- `threat_model.md` – STRIDE threat model
- `attack_logs.md` – Simulated attacks and the logs they produced

## How the changes were verified

The security controls were tested manually against a running server.
I created two users (Alice and Bob), ran the attacks with curl, and checked the container logs.

The attacks and the resulting log lines are documented in `attack_logs.md`.
The curl commands used for each test are included there so the steps can be followed.