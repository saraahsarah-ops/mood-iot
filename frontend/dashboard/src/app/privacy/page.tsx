"use client";

import Link from "next/link";

const sections = [
  {
    title: "1. Responsable du traitement",
    content: (
      <>
        <p>
          Le responsable du traitement des donnees est <strong>Mood-IoT</strong>,
          projet universitaire developpe dans le cadre du Master ADE 2026. Le
          traitement est effectue sous la supervision de l'equipe pedagogique et
          dans le respect du Reglement General sur la Protection des Donnees
          (RGPD — Reglement UE 2016/679).
        </p>
      </>
    ),
  },
  {
    title: "2. Donnees collectees",
    content: (
      <>
        <p className="mb-3">
          Dans le cadre du suivi psychiatrique a distance, les donnees suivantes
          peuvent etre collectees via les capteurs IoT et l'application mobile :
        </p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>Frequence cardiaque (FC moyenne quotidienne)</li>
          <li>Variabilite de la frequence cardiaque (HRV)</li>
          <li>Duree de sommeil et qualite du sommeil</li>
          <li>Nombre de pas quotidiens</li>
          <li>Localisation GPS (rayon de deplacement, non coordonnees exactes)</li>
          <li>Temps d'ecran quotidien</li>
          <li>Nombre et duree des appels telephoniques</li>
        </ul>
        <p className="mt-3">
          Les reponses aux questionnaires PHQ-9 (evaluation de la depression)
          sont egalement collectees lors des auto-evaluations du patient.
        </p>
      </>
    ),
  },
  {
    title: "3. Finalites du traitement",
    content: (
      <ul className="list-disc space-y-1.5 pl-5">
        <li>
          <strong>Suivi psychiatrique a distance</strong> : permettre au
          psychiatre referent de suivre l'evolution de l'etat du patient entre
          les consultations.
        </li>
        <li>
          <strong>Detection precoce de rechute</strong> : calcul d'un score de
          risque (0-100) par un modele d'apprentissage automatique, avec alertes
          automatiques selon trois niveaux d'escalade.
        </li>
        <li>
          <strong>Coaching IA personnalise</strong> : recommandations
          comportementales generees par intelligence artificielle (Anthropic
          Claude) adaptees au profil du patient.
        </li>
      </ul>
    ),
  },
  {
    title: "4. Base legale",
    content: (
      <ul className="list-disc space-y-1.5 pl-5">
        <li>
          <strong>Consentement explicite du patient</strong> (Article 6.1.a du
          RGPD) : le patient donne son accord libre, specifique, eclaire et
          univoque avant toute collecte de donnees. Le consentement peut etre
          retire a tout moment.
        </li>
        <li>
          <strong>Interet vital</strong> (Article 6.1.d du RGPD) : pour les
          alertes de niveau 3 (score critique &ge; 80/100), le traitement peut
          etre effectue sans consentement prealable afin de proteger les interets
          vitaux du patient.
        </li>
        <li>
          <strong>Donnees de sante</strong> (Article 9.2.h du RGPD) : le
          traitement est necessaire a la gestion des systemes de soins de sante.
        </li>
      </ul>
    ),
  },
  {
    title: "5. Duree de conservation",
    content: (
      <ul className="list-disc space-y-1.5 pl-5">
        <li>
          <strong>Donnees de sante identifiantes</strong> : conservees 24 mois
          apres la derniere activite du patient sur la plateforme, puis
          anonymisees ou supprimees.
        </li>
        <li>
          <strong>Donnees anonymisees</strong> : conservees sans limite de duree
          a des fins de recherche et d'amelioration des modeles de scoring.
        </li>
        <li>
          <strong>Journaux d'audit</strong> : conserves 12 mois a des fins de
          securite et de tracabilite.
        </li>
      </ul>
    ),
  },
  {
    title: "6. Droits des personnes",
    content: (
      <>
        <p className="mb-3">
          Conformement au RGPD, vous disposez des droits suivants :
        </p>
        <ul className="list-disc space-y-1.5 pl-5">
          <li>
            <strong>Droit d'acces</strong> (Art. 15) : obtenir une copie de vos
            donnees personnelles.
          </li>
          <li>
            <strong>Droit de rectification</strong> (Art. 16) : corriger des
            donnees inexactes.
          </li>
          <li>
            <strong>Droit a l'effacement</strong> (Art. 17) : demander la
            suppression de vos donnees. La plateforme procede alors a
            l'anonymisation du dossier.
          </li>
          <li>
            <strong>Droit a la portabilite</strong> (Art. 20) : recevoir vos
            donnees dans un format structure et lisible par machine (export
            JSON).
          </li>
          <li>
            <strong>Droit d'opposition</strong> (Art. 21) : vous opposer au
            traitement de vos donnees.
          </li>
        </ul>
        <p className="mt-3">
          Pour exercer vos droits, contactez le Delegue a la Protection des
          Donnees :{" "}
          <a
            href="mailto:info@mood-iot.fr"
            className="font-medium text-primary-600 hover:underline"
          >
            info@mood-iot.fr
          </a>
        </p>
      </>
    ),
  },
  {
    title: "7. Securite",
    content: (
      <ul className="list-disc space-y-1.5 pl-5">
        <li>
          <strong>Chiffrement TLS 1.3</strong> en transit pour toutes les
          communications, et <strong>chiffrement applicatif (Fernet)</strong>
          des champs de sante sensibles au repos : diagnostic, notes cliniques,
          messages et transcriptions.
        </li>
        <li>
          <strong>Authentification JWT</strong> avec tokens a duree de vie
          limitee et support de l'authentification multi-facteurs (TOTP).
        </li>
        <li>
          <strong>Audit des acces</strong> : les consultations, modifications et
          exports de donnees sensibles sont enregistres dans un journal d'audit
          horodate, conserve a des fins de securite et de tracabilite.
        </li>
        <li>
          <strong>Controle d'acces base sur les roles</strong> (RBAC) : seuls les
          psychiatres referents peuvent acceder aux dossiers de leurs patients.
        </li>
      </ul>
    ),
  },
  {
    title: "8. Sous-traitants",
    content: (
      <>
        <p className="mb-3">
          Les sous-traitants suivants peuvent acceder aux donnees dans le cadre
          de leurs prestations :
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="pb-2 pr-4 font-semibold text-gray-700">
                  Sous-traitant
                </th>
                <th className="pb-2 pr-4 font-semibold text-gray-700">
                  Finalite
                </th>
                <th className="pb-2 font-semibold text-gray-700">
                  Localisation
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="py-2 pr-4">Hetzner Online GmbH</td>
                <td className="py-2 pr-4">Hebergement et base de donnees</td>
                <td className="py-2">Allemagne (UE)</td>
              </tr>
              <tr>
                <td className="py-2 pr-4">Anthropic</td>
                <td className="py-2 pr-4">Coaching IA (API Claude)</td>
                <td className="py-2">USA</td>
              </tr>
              <tr>
                <td className="py-2 pr-4">OVHcloud (OVH SAS)</td>
                <td className="py-2 pr-4">Envoi de SMS d'alerte</td>
                <td className="py-2">France (UE)</td>
              </tr>
              <tr>
                <td className="py-2 pr-4">Resend</td>
                <td className="py-2 pr-4">Emails transactionnels</td>
                <td className="py-2">USA</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-gray-500">
          Des clauses contractuelles types (SCC) sont en place pour les
          transferts hors UE conformement au chapitre V du RGPD.
        </p>
      </>
    ),
  },
  {
    title: "9. Cookies",
    content: (
      <p>
        La plateforme Mood-IoT utilise uniquement des{" "}
        <strong>cookies techniques</strong> strictement necessaires au
        fonctionnement du service : gestion de la session utilisateur,
        preferences d'interface et jetons d'authentification. Aucun cookie
        publicitaire, de pistage ou d'analyse comportementale n'est utilise.
      </p>
    ),
  },
  {
    title: "10. Contact DPO",
    content: (
      <>
        <p>
          Pour toute question relative a la protection de vos donnees
          personnelles, vous pouvez contacter le Delegue a la Protection des
          Donnees :
        </p>
        <div className="mt-3 rounded-lg bg-gray-50 px-4 py-3">
          <p className="font-medium text-gray-700">
            Delegue a la Protection des Donnees — Mood-IoT
          </p>
          <p className="mt-1 text-gray-500">
            Email :{" "}
            <a
              href="mailto:info@mood-iot.fr"
              className="font-medium text-primary-600 hover:underline"
            >
              info@mood-iot.fr
            </a>
          </p>
        </div>
      </>
    ),
  },
];

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-3xl py-8">
      {/* Back button */}
      <Link
        href="/"
        className="mb-6 inline-flex items-center gap-1.5 text-[13px] font-medium text-gray-500 transition-colors hover:text-gray-700"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="h-4 w-4"
        >
          <path
            fillRule="evenodd"
            d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
            clipRule="evenodd"
          />
        </svg>
        Retour au tableau de bord
      </Link>

      {/* Page title */}
      <h1 className="mb-2 text-2xl font-bold text-gray-900">
        Politique de Confidentialite
      </h1>
      <p className="mb-8 text-[13px] text-gray-400">
        Derniere mise a jour : mai 2026
      </p>

      {/* Sections */}
      <div className="space-y-5">
        {sections.map((section) => (
          <section
            key={section.title}
            className="rounded-xl bg-white px-6 py-5 shadow-sm ring-1 ring-gray-100"
          >
            <h2 className="mb-3 text-[15px] font-semibold text-gray-800">
              {section.title}
            </h2>
            <div className="text-[13px] leading-relaxed text-gray-600">
              {section.content}
            </div>
          </section>
        ))}
      </div>

      {/* Footer note */}
      <p className="mt-8 text-center text-[12px] text-gray-400">
        Mood-IoT — Projet universitaire Master ADE 2026
      </p>
    </div>
  );
}
