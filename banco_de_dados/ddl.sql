-- Projeto: VozCidadão
-- Banco de dados: vozcidadao
-- Compatível com MySQL 8.0+
-- DDL: estrutura do banco, tabelas e view.

CREATE DATABASE IF NOT EXISTS vozcidadao
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE vozcidadao;

-- Remove objetos na ordem correta para permitir executar o DDL novamente.
DROP VIEW IF EXISTS vw_unidades_servicos_horarios;
DROP TABLE IF EXISTS horarios_atendimento;
DROP TABLE IF EXISTS unidade_servico;
DROP TABLE IF EXISTS servicos;
DROP TABLE IF EXISTS unidades_saude;

CREATE TABLE unidades_saude (
    id_unidade INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    tipo ENUM('HOSPITAL', 'UPA', 'UBS', 'POLICLINICA', 'CAPS')
        NOT NULL,
    unidade_publica BOOLEAN NOT NULL DEFAULT TRUE,
    endereco VARCHAR(255) NOT NULL,
    bairro VARCHAR(100) NOT NULL,
    cidade VARCHAR(100) NOT NULL,
    uf CHAR(2) NOT NULL,
    cep VARCHAR(9),
    telefone VARCHAR(20),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    atendimento_24h BOOLEAN NOT NULL DEFAULT FALSE,
    ativa BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_unidade_publica CHECK (unidade_publica = TRUE),
    INDEX idx_unidade_localizacao (cidade, bairro),
    INDEX idx_unidade_tipo (tipo)
) ENGINE=InnoDB;

CREATE TABLE servicos (
    id_servico INT AUTO_INCREMENT PRIMARY KEY,
    nome VARCHAR(120) NOT NULL,
    descricao VARCHAR(500),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE KEY uk_servico_nome (nome)
) ENGINE=InnoDB;

CREATE TABLE unidade_servico (
    id_unidade INT NOT NULL,
    id_servico INT NOT NULL,
    observacoes VARCHAR(255),
    PRIMARY KEY (id_unidade, id_servico),
    CONSTRAINT fk_us_unidade
        FOREIGN KEY (id_unidade) REFERENCES unidades_saude(id_unidade)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT fk_us_servico
        FOREIGN KEY (id_servico) REFERENCES servicos(id_servico)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

CREATE TABLE horarios_atendimento (
    id_horario INT AUTO_INCREMENT PRIMARY KEY,
    id_unidade INT NOT NULL,
    dia_semana ENUM(
        'SEGUNDA', 'TERCA', 'QUARTA', 'QUINTA',
        'SEXTA', 'SABADO', 'DOMINGO'
    ) NOT NULL,
    hora_abertura TIME,
    hora_fechamento TIME,
    fechado BOOLEAN NOT NULL DEFAULT FALSE,
    observacoes VARCHAR(255),
    CONSTRAINT fk_horario_unidade
        FOREIGN KEY (id_unidade) REFERENCES unidades_saude(id_unidade)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT uk_unidade_dia UNIQUE (id_unidade, dia_semana),
    CONSTRAINT chk_horario_valido CHECK (
        (fechado = TRUE AND hora_abertura IS NULL AND hora_fechamento IS NULL)
        OR
        (fechado = FALSE AND hora_abertura IS NOT NULL AND hora_fechamento IS NOT NULL)
    )
) ENGINE=InnoDB;

-- View para consultar unidades, serviços oferecidos e horários.
-- Uma unidade pode aparecer em várias linhas (uma por serviço/horário).
CREATE VIEW vw_unidades_servicos_horarios AS
SELECT
    u.id_unidade,
    u.nome AS unidade,
    u.tipo,
    u.unidade_publica,
    u.endereco,
    u.bairro,
    u.cidade,
    u.uf,
    u.latitude,
    u.longitude,
    u.atendimento_24h,
    s.id_servico,
    s.nome AS servico,
    h.dia_semana,
    h.hora_abertura,
    h.hora_fechamento,
    h.fechado,
    h.observacoes AS observacao_horario
FROM unidades_saude AS u
LEFT JOIN unidade_servico AS us
    ON us.id_unidade = u.id_unidade
LEFT JOIN servicos AS s
    ON s.id_servico = us.id_servico
LEFT JOIN horarios_atendimento AS h
    ON h.id_unidade = u.id_unidade
WHERE u.ativa = TRUE AND u.unidade_publica = TRUE;
