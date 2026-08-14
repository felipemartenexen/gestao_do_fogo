"""
Ponte entre o perfil da conta (/users/profile/) e o perfil de pesquisador.

Fica separado das views para que `apps.users` consiga montar a seção de pesquisador
sem depender de nada de HTTP daqui.
"""

from apps.users.models import CustomUser

from .forms import ResearcherProfileForm
from .models import Researcher


def get_profile(user: CustomUser) -> Researcher | None:
    """
    Perfil de pesquisador do usuário, assumindo automaticamente o que veio do formulário.

    Quem respondeu o mapeamento e depois criou conta com o mesmo e-mail encontra a ficha
    já preenchida, em vez de começar do zero.
    """
    if not user.is_authenticated:
        return None

    researcher = getattr(user, "researcher_profile", None)
    if researcher is not None:
        return researcher

    unclaimed = Researcher.objects.filter(email__iexact=user.email, user__isnull=True).first()
    if unclaimed is not None:
        unclaimed.user = user
        unclaimed.save(update_fields=["user", "updated_at"])
    return unclaimed


def profile_context(user: CustomUser, form: ResearcherProfileForm | None = None) -> dict:
    """Contexto da seção de pesquisador. `form` vem preenchido quando houve erro de validação."""
    researcher = get_profile(user)
    return {
        "researcher": researcher,
        "researcher_form": form or ResearcherProfileForm(instance=researcher),
    }
