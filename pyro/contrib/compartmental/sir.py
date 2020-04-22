
class SIRModel(CompartmentalModel):
    def __init__(self, population, recovery_time, data):
        compartments = ("S", "I")  # R is implicit.
        duration = len(data)
        super().__init__(self, compartments, duration, population)

        assert isinstance(recovery_time, float)
        assert recovery_time > 0
        self.recovery_time = recovery_time

        self.data = data

    def global_model(self):
        tau = self.recovery_time
        R0 = pyro.sample("R0", dist.LogNormal(0., 1.))
        rho = pyro.sample("rho", dist.Uniform(0, 1))

        # Convert interpretable parameters to distribution parameters.
        rate_s = -R0 / (tau * population)
        prob_i = 1 / (1 + tau)

        return rate_s, prob_i, rho

    def initialize(self, params):
        return {"S": 1. - self.population, "I": 1.}

    def transition_fwd(self, params, state, t):
        rate_s, prob_i, rho = params

        S2I = pyro.sample("S2I_{}".format(t),
                          dist.Binomial(state["S"], -(rate_s * I).expm1()))
        I2R = pyro.sample("I2R_{}".format(t),
                          dist.Binomial(state["I"], prob_i))

        state["S"] = pyro.deterministic("S_{}".format(t), state["S"] - S2I)
        state["I"] = pyro.deterministic("I_{}".format(t), state["I"] + S2I - I2R)

        pyro.sample("obs_{}".format(t),
                    dist.ExtendedBinomial(S2I, rho),
                    obs=self.data[t])

    def transition_bwd(self, params, prev, curr):
        rate_s, prob_i, rho = params

        # Reverse the S2I,I2R computation.
        S2I = prev["S"] - curr["S"]
        I2R = prev["I"] - curr["I"] + S2I

        # Compute probability factors.
        S2I_logp = dist.ExtendedBinomial(S_prev, -(rate_s * I_prev).expm1()).log_prob(S2I)
        I2R_logp = dist.ExtendedBinomial(I_prev, prob_i).log_prob(I2R)
        # FIXME the following line needs to .unsqueeze() data for enumeration.
        obs_logp = dist.ExtendedBinomial(S2I.clamp(min=0), rho).log_prob(self.data)
        return obs_logp + S2I_logp + I2R_logp
