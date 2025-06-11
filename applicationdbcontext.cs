using System.Data.Entity;

namespace WebSystem.Models
{
    public class ApplicationDbContext : DbContext
    {
        public DbSet<Cliente> Clientes { get; set; }
    }
}
