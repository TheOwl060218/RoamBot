type PlaceholderPageProps = {
  title: string
}

export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <section className="placeholder-page">
      <h1>{title}</h1>
    </section>
  )
}
