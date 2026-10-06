interface Props {
  titulo: string;
  descricao: string;
  userStories: string[];
}

/** Placeholder padrão das telas ainda não implementadas — mantém lede e visual do protótipo. */
export function EmConstrucao({ titulo, descricao, userStories }: Props) {
  return (
    <section className="screen">
      <div className="page-lede">
        <h2 style={{ fontSize: 20 }}>{titulo}</h2>
        <p>{descricao}</p>
      </div>
      <div className="layer-banner">
        <i className="fa-solid fa-circle-info" />
        Tela em construção. A referência visual é o Protótipo V1 validado em 17/09
        (prototipos/prototipoV1.html).
      </div>
      <div className="panel">
        <div className="panel-head">
          <div>
            <h3>Histórias de usuário desta tela</h3>
            <div className="sub">Critérios de aceite no Backlog v2</div>
          </div>
        </div>
        <div className="panel-body" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {userStories.map((us) => (
            <span key={us} className="badge badge-blue">{us}</span>
          ))}
        </div>
      </div>
    </section>
  );
}
